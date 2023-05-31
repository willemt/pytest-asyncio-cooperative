from .conftest import includes_lines_in_order


def test_generator_function(testdir):
    testdir.makepyfile(
        """
        import pytest


        @pytest.fixture
        def outer():
            print("outer: setup")
            yield
            print("outer: cleanup")


        @pytest.fixture
        def inner(outer):
            print("inner: setup")
            yield
            print("inner: cleanup")


        @pytest.mark.asyncio_cooperative
        async def test_async(inner) -> None:
            pass

    """
    )

    result = testdir.runpytest()

    expected_lines = [
        "outer: setup",
        "inner: setup",
        "inner: cleanup",
        "outer: cleanup",
    ]

    result = testdir.runpytest()
    assert includes_lines_in_order(expected_lines, result.stdout.lines)


def test_async_generator_function(testdir):
    testdir.makepyfile(
        """
        import pytest


        @pytest.fixture
        async def outer():
            print("outer: setup")
            yield
            print("outer: cleanup")


        @pytest.fixture
        async def inner(outer):
            print("inner: setup")
            yield
            print("inner: cleanup")


        @pytest.mark.asyncio_cooperative
        async def test_async(inner) -> None:
            pass

    """
    )

    result = testdir.runpytest()

    expected_lines = [
        "outer: setup",
        "inner: setup",
        "inner: cleanup",
        "outer: cleanup",
    ]

    result = testdir.runpytest()
    assert includes_lines_in_order(expected_lines, result.stdout.lines)


def test_generator_function_with_sibling(testdir):
    testdir.makepyfile(
        """
        import pytest


        @pytest.fixture
        def outer(request):
            print(f"outer: setup {request.function.__name__}")
            yield
            print(f"outer: cleanup {request.function.__name__}")


        @pytest.fixture
        def middle_sibling(outer, request):
            print(f"middle_sibling: setup {request.function.__name__}")
            yield
            print(f"middle_sibling: cleanup {request.function.__name__}")


        @pytest.fixture
        def middle(outer, middle_sibling, request):
            print(f"middle: setup {request.function.__name__}")
            yield
            print(f"middle: cleanup {request.function.__name__}")


        @pytest.mark.asyncio_cooperative
        async def test_async(middle) -> None:
            print("test_async")

    """
    )

    result = testdir.runpytest()

    expected_lines = [
        "outer: setup test_async",
        "middle_sibling: setup test_async",
        "middle: setup test_async",
        "test_async",
        "middle: cleanup test_async",
        "middle_sibling: cleanup test_async",
        "outer: cleanup test_async",
    ]

    result = testdir.runpytest()
    assert includes_lines_in_order(expected_lines, result.stdout.lines)


def test_async_generator_function_with_sibling_and_another_test(testdir):
    testdir.makepyfile(
        """
        import asyncio

        import pytest


        @pytest.fixture
        async def outer(request):
            print(f"outer: setup {request.function.__name__}")
            yield
            print(f"outer: cleanup {request.function.__name__}")


        @pytest.fixture
        async def middle_sibling(outer, request):
            print(f"middle_sibling: setup {request.function.__name__}")
            yield
            print(f"middle_sibling: cleanup {request.function.__name__}")


        @pytest.fixture
        async def middle(outer, middle_sibling, request):
            print(f"middle: setup {request.function.__name__}")
            yield
            print(f"middle: cleanup {request.function.__name__}")


        @pytest.mark.asyncio_cooperative
        async def test_async(middle) -> None:
            await asyncio.sleep(0.5)
            print("test_a")

        @pytest.mark.asyncio_cooperative
        async def test_b(middle) -> None:
            await asyncio.sleep(0.1)
            print("test_b")
    """
    )

    result = testdir.runpytest()

    expected_lines = [
        "outer: setup test_async",
        "middle_sibling: setup test_async",
        "middle: setup test_async",
        "outer: setup test_b",
        "middle_sibling: setup test_b",
        "middle: setup test_b",
        "test_b",
        "middle: cleanup test_b",
        "middle_sibling: cleanup test_b",
        "outer: cleanup test_b",
        "test_async_generator_function_with_sibling_and_another_test.py .test_a",
        "middle: cleanup test_async",
        "middle_sibling: cleanup test_async",
        "outer: cleanup test_async",
    ]

    result = testdir.runpytest()
    assert includes_lines_in_order(expected_lines, result.stdout.lines)


def test_generator_function_with_sibling_and_another_test(testdir):
    testdir.makepyfile(
        """
        import asyncio

        import pytest


        @pytest.fixture
        def outer(request):
            print(f"outer: setup {request.function.__name__}")
            yield
            print(f"outer: cleanup {request.function.__name__}")


        @pytest.fixture
        def middle_sibling(outer, request):
            print(f"middle_sibling: setup {request.function.__name__}")
            yield
            print(f"middle_sibling: cleanup {request.function.__name__}")


        @pytest.fixture
        def middle(outer, middle_sibling, request):
            print(f"middle: setup {request.function.__name__}")
            yield
            print(f"middle: cleanup {request.function.__name__}")


        @pytest.mark.asyncio_cooperative
        async def test_async(middle) -> None:
            await asyncio.sleep(0.5)
            print("test_a")

        @pytest.mark.asyncio_cooperative
        async def test_b(middle) -> None:
            await asyncio.sleep(0.1)
            print("test_b")
    """
    )

    result = testdir.runpytest()

    expected_lines = [
        "outer: setup test_async",
        "middle_sibling: setup test_async",
        "middle: setup test_async",
        "outer: setup test_b",
        "middle_sibling: setup test_b",
        "middle: setup test_b",
        "test_b",
        "middle: cleanup test_b",
        "middle_sibling: cleanup test_b",
        "outer: cleanup test_b",
        "test_generator_function_with_sibling_and_another_test.py .test_a",
        "middle: cleanup test_async",
        "middle_sibling: cleanup test_async",
        "outer: cleanup test_async",
    ]

    result = testdir.runpytest()
    assert includes_lines_in_order(expected_lines, result.stdout.lines)


def test_session_scope_gen(testdir):
    testdir.makepyfile(
        """
        import pytest
        import asyncio

        @pytest.fixture(scope="session")
        def outer():
            print("outer: setup")
            yield
            print("outer: cleanup")


        @pytest.fixture
        def inner(outer):
            print("inner: setup")
            yield
            print("inner: cleanup")

        @pytest.mark.asyncio_cooperative
        async def test_async_0(inner) -> None:
            await asyncio.sleep(0.1)


        @pytest.mark.asyncio_cooperative
        async def test_async_1(inner) -> None:
            await asyncio.sleep(0.1)
    """
    )

    result = testdir.runpytest()

    expected_lines = [
        "outer: setup",
        "inner: setup",
        "inner: setup",
        "inner: cleanup",
        "inner: cleanup",
        "outer: cleanup",
    ]

    result = testdir.runpytest()
    assert includes_lines_in_order(expected_lines, result.stdout.lines)

    
def test_session_scope_async_gen(testdir):
    testdir.makepyfile(
        """
        import pytest
        import asyncio

        @pytest.fixture(scope="session")
        async def outer():
            print("outer: setup")
            yield
            print("outer: cleanup")


        @pytest.fixture
        def inner(outer):
            print("inner: setup")
            yield
            print("inner: cleanup")


        @pytest.mark.asyncio_cooperative
        async def test_async_0(inner) -> None:
            await asyncio.sleep(0.1)


        @pytest.mark.asyncio_cooperative
        async def test_async_1(inner) -> None:
            await asyncio.sleep(0.1)
    """
    )

    result = testdir.runpytest()

    expected_lines = [
        "outer: setup",
        "inner: setup",
        "inner: setup",
        "inner: cleanup",
        "inner: cleanup",
        "outer: cleanup",
    ]

    result = testdir.runpytest()
    assert includes_lines_in_order(expected_lines, result.stdout.lines)
