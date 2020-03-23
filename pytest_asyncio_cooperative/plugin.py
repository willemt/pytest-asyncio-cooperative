import asyncio
import inspect
import time

import pytest


@pytest.hookspec
def pytest_runtest_makereport(item, call):
    # Tests are run outside of the normal place, so we have to inject our timings

    if call.when == "call":
        if hasattr(item, "start") and hasattr(item, "stop"):
            call.start = item.start
            call.stop = item.stop

    elif call.when == "setup":
        if hasattr(item, "start_setup") and hasattr(item, "stop_setup"):
            call.start = item.start_setup
            call.stop = item.stop_setup

    elif call.when == "teardown":
        if hasattr(item, "start_teardown") and hasattr(item, "stop_teardown"):
            call.start = item.start_teardown
            call.stop = item.stop_teardown


def not_coroutine_failure(*args, **kwargs):
    raise Exception("is not a coroutine. Add the async keyword to make it one")


def function_args(func):
    return func.__code__.co_varnames[: func.__code__.co_argcount]


async def _fill_fixture_fixtures(_fixtureinfo, fixture):
    values = []
    all_teardowns = []
    for arg_name in function_args(fixture.func):
        assert len(_fixtureinfo.name2fixturedefs[arg_name]) == 1
        dep_fixture = _fixtureinfo.name2fixturedefs[arg_name][0]
        value, teardowns = await fill_fixture_fixtures(_fixtureinfo, dep_fixture)
        values.append(value)
        all_teardowns.extend(teardowns)
    return values, all_teardowns


class CachedFunction(object):
    def __init__(self, wrapped_func):
        self.lock = asyncio.Lock()
        self.wrapped_func = wrapped_func

    @property
    def __code__(self):
        return self.wrapped_func.__code__

    @property
    def __name__(self):
        return self.wrapped_func.__name__


class CachedFunction(CachedFunction):
    async def __call__(self, *args):
        async with self.lock:
            if hasattr(self, "value"):
                return self.value
            value = await self.wrapped_func(*args)
            self.value = value
            return value


class AsyncGenCounter:
    def __init__(self, parent):
        self.num_calls = 0
        self.parent = parent

    def __aiter__(self):
        return self

    async def __anext__(self):
        self.num_calls += 1
        if self.num_calls == 2:
            self.parent.completed(self)
        return await self.parent.__anext__()


class CachedAsyncGen(CachedFunction):
    """Save the result of the 1st yield.
    Yield 2nd yield when all callers have yielded."""

    def __init__(self, wrapped_func):
        super().__init__(wrapped_func)
        self.instances = set()

    def completed(self, instance):
        self.instances.remove(instance)

    def __call__(self, *args):
        self.args = args
        instance = AsyncGenCounter(self)
        self.instances.add(instance)
        return instance

    async def __anext__(self):
        if len(self.instances) == 0:
            return await self.gen.__anext__()
        async with self.lock:
            if hasattr(self, "value"):
                return self.value
            else:
                gen = self.wrapped_func(*self.args)
                self.gen = gen
                self.value = await gen.__anext__()
                return self.value


async def fill_fixture_fixtures(_fixtureinfo, fixture):

    if inspect.isasyncgenfunction(fixture.func) or isinstance(
        fixture.func, CachedAsyncGen
    ):
        fixture_values, teardowns = await _fill_fixture_fixtures(_fixtureinfo, fixture)

        # Cache the module call
        if fixture.scope in ["module"]:
            if not isinstance(fixture.func, CachedAsyncGen):
                fixture.func = CachedAsyncGen(fixture.func)

        gen = fixture.func(*fixture_values)
        value = await gen.__anext__()
        return value, teardowns + [gen]

    elif inspect.iscoroutinefunction(fixture.func) or isinstance(
        fixture.func, CachedFunction
    ):
        fixture_values, teardowns = await _fill_fixture_fixtures(_fixtureinfo, fixture)

        # Cache the module call
        if fixture.scope in ["module"]:
            if not isinstance(fixture.func, CachedFunction):
                fixture.func = CachedFunction(fixture.func)

        value = await fixture.func(*fixture_values)
        return value, teardowns

    else:
        raise Exception(
            f"Provided a fixture '{fixture.func.__name__}' that is not a coroutine.\n"
            "Remove the fixture or add the 'async' keyword to the fixture"
        )


async def fill_fixtures(item):
    fixture_values = []
    teardowns = []
    for arg_name in function_args(item.function):
        # FIXME: not sure how to handle duplicate fixture names
        assert len(item._fixtureinfo.name2fixturedefs[arg_name]) == 1
        fixture = item._fixtureinfo.name2fixturedefs[arg_name][0]

        if fixture.scope not in ["function", "module"]:
            raise Exception(f"{fixture.scope} scope not supported")

        value, teardowns2 = await fill_fixture_fixtures(item._fixtureinfo, fixture)
        teardowns.extend(teardowns2)
        fixture_values.append(value)

    # Slight hack to stop the regular fixture logic from running
    item.fixturenames = []

    return fixture_values, teardowns


async def test_wrapper(item):
    # Do setup
    item.start_setup = time.time()
    fixture_values, teardowns = await fill_fixtures(item)
    item.stop_setup = time.time()

    # Run test
    item.start = time.time()
    await item.function(*fixture_values)
    item.stop = time.time()

    # Do teardowns
    item.start_teardown = time.time()
    for teardown in teardowns:
        try:
            await teardown.__anext__()
        except StopAsyncIteration:
            pass
    item.stop_teardown = time.time()


@pytest.hookspec
def pytest_runtestloop(session):
    session.wrapped_fixtures = {}

    # Collect our coroutines
    regular_items = []
    item_by_coro = {}
    tasks = []
    for item in session.items:
        markers = [m.name for m in item.own_markers]
        if "asyncio_cooperative" in markers:
            if inspect.iscoroutinefunction(item.function):
                task = test_wrapper(item)
                item_by_coro[task] = item
                tasks.append(task)
            else:
                item.runtest = not_coroutine_failure
                item.ihook.pytest_runtest_protocol(item=item, nextitem=None)
        else:
            regular_items.append(item)

    async def run_tests(tasks):
        completed = []
        while tasks:
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            tasks = list(pending)

            for result in done:
                item = item_by_coro[result._coro]
                item.runtest = lambda: result.result()
                item.ihook.pytest_runtest_protocol(item=item, nextitem=None)

            completed.extend(done)

        return completed

    # Run the tests using cooperative multitasking
    loop = asyncio.new_event_loop()
    try:
        task = run_tests(tasks)
        loop.run_until_complete(task)
    finally:
        loop.close()

    session.items = regular_items
