import asyncio
import functools
import inspect
import time

import pytest

from .assertion import activate_assert_rewrite


def pytest_addoption(parser):
    parser.addoption(
        "--max-asyncio-tasks",
        action="store",
        default=100,
        help="asyncio: maximum number of tasks to run concurrently (int)",
    )
    parser.addoption(
        "--asyncio-task-timeout",
        action="store",
        default=120,
        help="asyncio: number of seconds before a test will be cancelled (int)",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "asyncio_cooperative: run an async test cooperatively with other async tests.",
    )
    config.addinivalue_line(
        "markers", "flakey: if this test fails then run it one more time."
    )


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


def not_coroutine_failure(function_name: str, *args, **kwargs):
    raise Exception(
        f"Function {function_name} is not a coroutine.\n"
        f"Tests with the `@pytest.mark.asyncio_cooperative` mark MUST be coroutines.\n"
        f"Please add the `async` keyword to the test function."
    )


def function_args(func):
    return func.__code__.co_varnames[: func.__code__.co_argcount]


async def _fill_fixture_fixtures(_fixtureinfo, fixture, item):
    values = []
    all_teardowns = []
    for arg_name in function_args(fixture.func):
        dep_fixture = _get_fixture(_fixtureinfo, arg_name)

        value, teardowns = await fill_fixture_fixtures(_fixtureinfo, dep_fixture, item)
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


async def fill_fixture_fixtures(_fixtureinfo, fixture, item):

    if inspect.isasyncgenfunction(fixture.func) or isinstance(
        fixture.func, CachedAsyncGen
    ):
        fixture_values, teardowns = await _fill_fixture_fixtures(
            _fixtureinfo, fixture, item
        )

        # Cache the module call
        if fixture.scope in ["module", "session"]:
            if not isinstance(fixture.func, CachedAsyncGen):
                fixture.func = CachedAsyncGen(fixture.func)

        gen = fixture.func(*fixture_values)
        value = await gen.__anext__()
        return value, teardowns + [gen]

    elif inspect.iscoroutinefunction(fixture.func) or isinstance(
        fixture.func, CachedFunction
    ):
        fixture_values, teardowns = await _fill_fixture_fixtures(
            _fixtureinfo, fixture, item
        )

        # Cache the module call
        if fixture.scope in ["module", "session"]:
            if not isinstance(fixture.func, CachedFunction):
                fixture.func = CachedFunction(fixture.func)

        value = await fixture.func(*fixture_values)
        return value, teardowns

    # Regular fixture
    # FIXME: we should use more of pytest's fixture system
    elif inspect.isgeneratorfunction(fixture.func):
        fixture_values, teardowns = await _fill_fixture_fixtures(
            _fixtureinfo, fixture, item
        )
        gen = fixture.func(*fixture_values)
        return gen.__next__(), teardowns + [gen]

    # It's a parameterization
    # FIXME: we should use more of pytest's fixture system
    elif fixture.params:
        request = item._request
        request.param = item._pyfuncitem.callspec.params[fixture.argname]
        val = fixture.func(request)
        return val, []

    # FIXME: we should use more of pytest's fixture system
    elif inspect.isfunction(fixture.func):
        fixture_values, teardowns = await _fill_fixture_fixtures(
            _fixtureinfo, fixture, item
        )
        val = fixture.func(*fixture_values)
        return val, teardowns

    else:
        raise Exception(
            f"Something is strange about the fixture '{fixture.func.__name__}'.\n"
            f"Please create an issue with reproducible sample on github."
        )


def _get_fixture(_fixtureinfo, arg_name):
    """
    Sometimes fixture names clash with plugin fixtures.
    We priortise fixtures that are defined inside the user's module
    """
    fixtures = sorted(
        _fixtureinfo.name2fixturedefs[arg_name], key=lambda x: not x.has_location
    )
    return fixtures[0]


async def fill_fixtures(item):
    fixture_values = []
    teardowns = []
    for arg_name in function_args(item.function):
        fixture = _get_fixture(item._fixtureinfo, arg_name)

        if fixture.scope not in ["function", "module", "session"]:
            raise Exception(f"{fixture.scope} scope not supported")

        value, teardowns2 = await fill_fixture_fixtures(
            item._fixtureinfo, fixture, item
        )
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
        if inspect.isgenerator(teardown):
            try:
                teardown.__next__()
            except StopIteration:
                pass
        else:
            try:
                await teardown.__anext__()
            except StopAsyncIteration:
                pass
    item.stop_teardown = time.time()


# TODO: move to hypothesis module
async def hypothesis_test_wrapper(item):
    """
    Hypothesis is synchronous, let's run inside an executor to keep asynchronicity
    """

    # Do setup
    item.start_setup = time.time()
    fixture_values, teardowns = await fill_fixtures(item)
    item.stop_setup = time.time()

    default_loop = asyncio.get_running_loop()
    inner_test = item.function.hypothesis.inner_test

    def async_to_sync(*args, **kwargs):
        # FIXME: can we cache this loop across multiple runs?
        loop = asyncio.new_event_loop()
        task = inner_test(*args, **kwargs)
        try:
            loop.run_until_complete(task)
        finally:
            loop.close()

    # Run test
    item.function.hypothesis.inner_test = async_to_sync
    wrapped_func_with_fixtures = functools.partial(item.function, *fixture_values)
    await default_loop.run_in_executor(None, wrapped_func_with_fixtures)

    # Do teardowns
    item.start_teardown = time.time()
    for teardown in teardowns:
        try:
            await teardown.__anext__()
        except StopAsyncIteration:
            pass
    item.stop_teardown = time.time()


class NotCoroutine(Exception):
    pass


def item_to_task(item):
    if inspect.iscoroutinefunction(item.function):
        return test_wrapper(item)
    elif getattr(item.function, "is_hypothesis_test", False):
        return hypothesis_test_wrapper(item)
    else:
        raise NotCoroutine


def _run_test_loop(tasks, session, run_tests):
    loop = asyncio.new_event_loop()
    try:
        task = run_tests(tasks, int(session.config.getoption("--max-asyncio-tasks")))
        loop.run_until_complete(task)
    finally:
        loop.close()


@pytest.hookspec
def pytest_runtestloop(session):
    if session.config.pluginmanager.is_registered("asyncio"):
        raise Exception(
            "pytest-asyncio-cooperative is NOT compatible with pytest-asyncio\n"
            "Uninstall pytest-asyncio or pass this option to pytest: `-p no:asyncio`\n"
        )

    session.wrapped_fixtures = {}

    flakes_to_retry = []

    # Collect our coroutines
    regular_items = []
    item_by_coro = {}
    tasks = []
    for item in session.items:
        markers = [m.name for m in item.own_markers]

        if "skip" in markers:
            continue

        # Coerce into a task
        if "asyncio_cooperative" in markers:
            try:
                task = item_to_task(item)
            except NotCoroutine:
                item.runtest = functools.partial(not_coroutine_failure, item.name)
                item.ihook.pytest_runtest_protocol(item=item, nextitem=None)
                continue

            item._flakey = "flakey" in markers
            item_by_coro[task] = item
            tasks.append(task)
        else:
            regular_items.append(item)

    async def run_tests(tasks, max_tasks):
        sidelined_tasks = tasks[max_tasks:]
        tasks = tasks[:max_tasks]

        task_timeout = int(session.config.getoption("--asyncio-task-timeout"))

        completed = []
        while tasks:

            # Mark when the task was started
            for task in tasks:
                if isinstance(task, asyncio.Task):
                    item = item_by_coro[task._coro]
                else:
                    item = item_by_coro[task]
                if not hasattr(item, "enqueue_time"):
                    item.enqueue_time = time.time()

            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED, timeout=30
            )

            # Cancel tasks that have taken too long
            tasks = []
            for task in pending:
                now = time.time()
                item = item_by_coro[task._coro]
                if task_timeout < now - item.enqueue_time:
                    task.cancel()
                tasks.append(task)

            for result in done:
                item = item_by_coro[result._coro]

                # Flakey tests will be run again if they failed
                # TODO: add retry count
                if item._flakey:
                    try:
                        result.result()
                    except:
                        item._flakey = None
                        new_task = item_to_task(item)
                        flakes_to_retry.append(new_task)
                        item_by_coro[new_task] = item
                        continue

                item.runtest = lambda: result.result()
                item.ihook.pytest_runtest_protocol(item=item, nextitem=None)
                # Hack: See rewrite comment below
                # pytest_runttest_protocl will disable the rewrite assertion
                # so we renable it here
                activate_assert_rewrite(item)

                completed.append(result)

            if sidelined_tasks:
                tasks.append(sidelined_tasks.pop(0))

        return completed

    # Do assert rewrite
    # Hack: pytest's implementation sets up assert rewriting as a shared
    # resource. This causes a race condition between async tests. Therefore we
    # need to activate the assert rewriting here
    if tasks:
        item = item_by_coro[tasks[0]]
        activate_assert_rewrite(item)

    # Run the tests using cooperative multitasking
    _run_test_loop(tasks, session, run_tests)

    # Run failed flakey tests
    if flakes_to_retry:
        _run_test_loop(flakes_to_retry, session, run_tests)

    # Hack: because we might be running synchronous tests later (ie.
    # regular_items) we to set this to zero otherwise pytest bails out early
    # NOTE: this doesn't work, the return code is not non-negative
    # if session.testsfailed:
    #     session.testsfailed = 0

    session.items = regular_items
