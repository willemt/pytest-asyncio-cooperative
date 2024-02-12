import asyncio
import inspect
from typing import List, Union

from _pytest.fixtures import FixtureDef, FixtureRequest


class Ignore(Exception):
    pass


def function_args(func):
    return func.__code__.co_varnames[: func.__code__.co_argcount]


def _get_fixture(item, arg_name, fixture=None):
    """
    Sometimes fixture names clash with plugin fixtures.
    We prioritise fixtures that are defined inside the user's module
    """
    if arg_name == "request":
        # Support parameterized fixture
        if fixture:
            try:
                item._request.param = item._pyfuncitem.callspec.params[fixture.argname]
            except (AttributeError, KeyError):
                pass

        return item._request

    if arg_name == "self":
        raise Ignore

    _fixtureinfo = item._fixtureinfo
    fixtures = sorted(
        _fixtureinfo.name2fixturedefs[arg_name], key=lambda x: x.has_location
    )
    return fixtures[-1]


async def fill_fixtures(item):
    fixture_values = []
    teardowns = []

    # Important to maintain order of fixtures specified by function
    fixture_names: List[str] = list(function_args(item.function))

    # Add fixtures not specified in function arguments (eg. autouse)
    for fixture_name in item._fixtureinfo.initialnames:
        if fixture_name not in fixture_names:
            fixture_names.append(fixture_name)

    fixtures = []
    are_autouse = []
    for fixture_name in fixture_names:
        try:
            fixture = _get_fixture(item, fixture_name)
        except Ignore:
            continue

        is_autouse = fixture_name not in function_args(item.function)

        if fixture.scope not in ["function", "module", "session"]:
            raise Exception(f"{fixture.scope} scope not supported")

        fixtures.append(fixture)
        are_autouse.append(is_autouse)

    # Fill fixtures concurrently
    fill_results = await asyncio.gather(
        *(
            fill_fixture_fixtures(item._fixtureinfo, fixture, item)
            for fixture in fixtures
        )
    )

    for (value, extra_teardowns), is_autouse in zip(fill_results, are_autouse):
        teardowns.extend(extra_teardowns)

        if not is_autouse:
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
    async def __call__(self, *args, **kwargs):
        async with self.lock:
            if hasattr(self, "value"):
                return self.value
            if hasattr(self, "exception"):
                raise self.exception
            try:
                if inspect.iscoroutinefunction(self.wrapped_func):
                    self.value = await self.wrapped_func(*args, **kwargs)
                else:
                    self.value = self.wrapped_func(*args, **kwargs)
            except Exception as e:
                self.exception = e
                raise
            return self.value


class GenCounter:
    def __init__(self, parent):
        self.num_calls = 0
        self.parent = parent

    def __iter__(self):
        return self

    def __next__(self):
        self.num_calls += 1
        if self.num_calls == 2:
            self.parent.completed(self)
        return self.parent.__next__()


class CachedGen(CachedFunctionBase):
    """Save the result of the 1st yield.
    Yield 2nd yield when all callers have yielded."""

    def __init__(self, wrapped_func):
        super().__init__(wrapped_func)
        self.instances = set()

    def completed(self, instance):
        self.instances.remove(instance)

    def __call__(self, *args):
        self.args = args
        instance = GenCounter(self)
        self.instances.add(instance)
        return instance

    def __next__(self):
        if len(self.instances) == 0:
            return self.gen.__next__()
        if hasattr(self, "value"):
            return self.value
        if hasattr(self, "exception"):
            raise self.exception
        else:
            try:
                gen = self.wrapped_func(*self.args)
                self.gen = gen
                self.value = gen.__next__()
            except Exception as e:
                self.exception = e
                raise
            return self.value


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
            if hasattr(self, "exception"):
                raise self.exception
            else:
                try:
                    gen = self.wrapped_func(*self.args)
                    self.gen = gen
                    self.value = await gen.__anext__()
                except Exception as e:
                    self.exception = e
                    raise
                return self.value


class CachedAsyncGenByArguments(CachedAsyncGen):
    """Save the result of the 1st yield.
    Yield 2nd yield when all callers have yielded.
    We cache based off arguments."""

    def __init__(self, wrapped_func):
        super().__init__(wrapped_func)
        self.callers_by_args = {}

    def __call__(self, *args):
        if args in self.callers_by_args:
            gen = self.callers_by_args[args]
        else:
            gen = CachedAsyncGen(self.wrapped_func)
            self.callers_by_args[args] = gen
        return gen(*args)


async def _make_asyncgen_fixture(_fixtureinfo, fixture: FixtureDef, item):
    fixture_values, teardowns = await _fill_fixture_fixtures(
        _fixtureinfo, fixture, item
    )

    func: Union[CachedAsyncGen, CachedAsyncGenByArguments]

    if fixture.scope in ["module", "session"]:
        if not isinstance(fixture.func, CachedAsyncGenByArguments):
            fixture.func = CachedAsyncGenByArguments(fixture.func)
        func = fixture.func

    elif fixture.scope in ["function"]:
        try:
            func = item._asyncio_cooperative_cached_functions[fixture]
        except AttributeError:
            func = CachedAsyncGen(fixture.func)
            item._asyncio_cooperative_cached_functions = {fixture: func}
        except KeyError:
            func = CachedAsyncGen(fixture.func)

        item._asyncio_cooperative_cached_functions[fixture] = func

    gen = func(*fixture_values)
    value = await gen.__anext__()
    return value, [gen] + teardowns


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
    fixture_values, teardowns = await _fill_fixture_fixtures(
        _fixtureinfo, fixture, item
    )

    if fixture.scope in ["module", "session"]:
        if not isinstance(fixture.func, CachedGen):
            fixture.func = CachedGen(fixture.func)
        func = fixture.func

    elif fixture.scope in ["function"]:
        try:
            func = item._asyncio_cooperative_cached_functions[fixture]
        except AttributeError:
            func = CachedGen(fixture.func)
            item._asyncio_cooperative_cached_functions = {fixture: func}
        except KeyError:
            func = CachedGen(fixture.func)

        item._asyncio_cooperative_cached_functions[fixture] = func

    gen = func(*fixture_values)
    return gen.__next__(), [gen] + teardowns


async def _make_regular_fixture(_fixtureinfo, fixture, item):
    # FIXME: we should use more of pytest's fixture system
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

    elif inspect.isgeneratorfunction(fixture.func) or isinstance(
        fixture.func, CachedGen
    ):
        return await _make_regular_generator_fixture(_fixtureinfo, fixture, item)

    elif inspect.isfunction(fixture.func):
        return await _make_regular_fixture(_fixtureinfo, fixture, item)

    else:
        raise Exception(
            f"Something is strange about the fixture '{fixture.func.__name__}'.\n"
            f"Please create an issue with reproducible sample on github."
        )
