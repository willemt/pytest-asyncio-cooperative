import inspect
import sys

import pytest

from pytest_asyncio_cooperative.fixtures import CachedGen


def my_function():
    yield "Hello, World!"


@pytest.mark.skipif(sys.version_info < (3, 10), reason="Requires Python 3.10+")
def test_isgeneratorfunction_duck_typing():
    wrapped = CachedGen(my_function)
    assert inspect.isgeneratorfunction(wrapped)
