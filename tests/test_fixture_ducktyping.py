import inspect

from pytest_asyncio_cooperative.fixtures import CachedGen


def my_function():
    yield "Hello, World!"


def test_isgeneratorfunction_duck_typing():
    wrapped = CachedGen(my_function)
    assert inspect.isgeneratorfunction(wrapped)
