import asyncio
import inspect

from _pytest.fixtures import FixtureRequest


class Ignore(Exception):
    pass


def function_args(func):
    return func.__code__.co_varnames[: func.__code__.co_argcount]


def _get_fixture(item, arg_name, fixture=None):
    """
    Sometimes fixture names clash with plugin fixtures.
    We priortise fixtures that are defined inside the user's module
    """
    if arg_name == "request":
        # Support parameterized fixture
        if fixture and fixture.params:
            item._request.param = item._pyfuncitem.callspec.params[fixture.argname]
        return item._request

    if arg_name == "self":
        raise Ignore

    _fixtureinfo = item._fixtureinfo
    fixtures = sorted(
        _fixtureinfo.name2fixturedefs[arg_name], key=lambda x: not x.has_location
    )
    return fixtures[0]


async def fill_fixtures(item):
    fixture_values = []
    teardowns = []
    for arg_name in function_args(item.function):
        try:
            fixture = _get_fixture(item, arg_name)
        except Ignore:
            continue

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


async def _fill_fixture_fixtures(_fixtureinfo, fixture, item):
    values = []
    all_teardowns = []
    for arg_name in function_args(fixture.func):
        try:
            dep_fixture = _get_fixture(item, arg_name, fixture)
        except Ignore:
            continue

        value, teardowns = await fill_fixture_fixtures(_fixtureinfo, dep_fixture, item)
        values.append(value)
        all_teardowns.extend(teardowns)
    return values, all_teardowns


class CachedFunctionBase(object):
    def __init__(self, wrapped_func):
        self.lock = asyncio.Lock()
        self.wrapped_func = wrapped_func

    @property
    def __code__(self):
        return self.wrapped_func.__code__

    @property
    def __name__(self):
        return self.wrapped_func.__name__


class CachedFunction(CachedFunctionBase):
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


class CachedAsyncGen(CachedFunctionBase):
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


async def _make_asyncgen_fixture(_fixtureinfo, fixture, item):
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


async def _make_coroutine_fixture(_fixtureinfo, fixture, item):
    fixture_values, teardowns = await _fill_fixture_fixtures(
        _fixtureinfo, fixture, item
    )

    # Cache the module call
    if fixture.scope in ["module", "session"]:
        if not isinstance(fixture.func, CachedFunction):
            fixture.func = CachedFunction(fixture.func)
        value = await fixture.func(*fixture_values)
    elif fixture.scope in ["function"]:
        try:
            func = item._asyncio_cooperative_cached_functions[fixture]
        except AttributeError:
            func = CachedFunction(fixture.func)
            item._asyncio_cooperative_cached_functions = {fixture: func}
        except KeyError:
            func = CachedFunction(fixture.func)

        item._asyncio_cooperative_cached_functions[fixture] = func

        value = await func(*fixture_values)
    else:
        raise Exception("unknown scope type")

    return value, teardowns


async def _make_regular_generator_fixture(_fixtureinfo, fixture, item):
    # FIXME: we should use more of pytest's fixture system
    fixture_values, teardowns = await _fill_fixture_fixtures(
        _fixtureinfo, fixture, item
    )
    gen = fixture.func(*fixture_values)
    return gen.__next__(), teardowns + [gen]


async def _make_regular_fixture(_fixtureinfo, fixture, item):
    # FIXME: we should use more of pytest's fixture system
    fixture_values, teardowns = await _fill_fixture_fixtures(
        _fixtureinfo, fixture, item
    )
    val = fixture.func(*fixture_values)
    return val, teardowns


async def fill_fixture_fixtures(_fixtureinfo, fixture, item):
    if isinstance(fixture, FixtureRequest):
        return fixture, []

    elif inspect.isasyncgenfunction(fixture.func) or isinstance(
        fixture.func, CachedAsyncGen
    ):
        return await _make_asyncgen_fixture(_fixtureinfo, fixture, item)

    elif inspect.iscoroutinefunction(fixture.func) or isinstance(
        fixture.func, CachedFunction
    ):
        return await _make_coroutine_fixture(_fixtureinfo, fixture, item)

    elif inspect.isgeneratorfunction(fixture.func):
        return await _make_regular_generator_fixture(_fixtureinfo, fixture, item)

    elif inspect.isfunction(fixture.func):
        return await _make_regular_fixture(_fixtureinfo, fixture, item)

    else:
        raise Exception(
            f"Something is strange about the fixture '{fixture.func.__name__}'.\n"
            f"Please create an issue with reproducible sample on github."
        )
