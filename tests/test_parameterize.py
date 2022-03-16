def test_parameterize_single(testdir):
    testdir.makeconftest("""""")

    testdir.makepyfile(
        """
        import asyncio
        import pytest


        @pytest.mark.asyncio_cooperative
        @pytest.mark.parametrize("number", [1, 2, 3])
        async def test_a(number):
            # print(number, flush=True)
            await asyncio.sleep(2)
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=3)


def test_parameterize_double(testdir):
    testdir.makeconftest("""""")

    testdir.makepyfile(
        """
        import asyncio
        import pytest


        @pytest.mark.asyncio_cooperative
        @pytest.mark.parametrize("number", [1, 2, 3])
        async def test_a(number):
            # print(number, flush=True)
            await asyncio.sleep(2)


        @pytest.mark.asyncio_cooperative
        async def test_b():
            await asyncio.sleep(2)
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=4)


def test_parameterize_cartesian(testdir):
    testdir.makepyfile(
        """
        import asyncio
        import pytest


        @pytest.mark.asyncio_cooperative
        @pytest.mark.parametrize("number", [1, 2, 3])
        @pytest.mark.parametrize("number2", [4, 5, 6])
        async def test_a(number, number2):
            # print(number, number2, flush=True)
            assert number in [1, 2, 3]
            assert number2 in [4, 5, 6]
            await asyncio.sleep(2)
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=9)


def test_parameterize_with_request(testdir):
    testdir.makeconftest("""""")

    testdir.makepyfile(
        """
        import asyncio
        import pytest


        @pytest.mark.asyncio_cooperative
        @pytest.mark.parametrize("number", [1, 2, 3])
        async def test_a(request, number):
            # print(number, flush=True)
            await asyncio.sleep(2)
    """
    )

    result = testdir.runpytest("-s")

    result.assert_outcomes(passed=3)


def test_request_with_params(testdir):
    testdir.makepyfile(
        """
        import asyncio
        import logging
        import time

        import pytest


        @pytest.fixture(scope="session", params=["A"])
        def fixture_A(request):
            return request.param


        @pytest.fixture(scope="session", params=["B"])
        def fixture_B(fixture_A, request):
            return request.param


        @pytest.mark.asyncio_cooperative
        async def test_async_01(fixture_B):
            param = fixture_B
            logging.info(f"time => {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}")
            await asyncio.sleep(5)
    """
    )

    result = testdir.runpytest("-s")

    result.assert_outcomes(passed=1)


def test_request_with_multi_params(testdir):
    testdir.makepyfile(
        """
        import asyncio
        import logging
        import time

        import pytest


        @pytest.fixture(scope="session", params=["A", "B"])
        def fixture_A(request):
            return request.param


        @pytest.fixture(scope="session", params=["1", "2"])
        def fixture_B(fixture_A, request):
            return request.param


        @pytest.mark.asyncio_cooperative
        async def test_async_01(fixture_B):
            param = fixture_B
            logging.info(f"time => {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}")
            await asyncio.sleep(5)
    """
    )

    result = testdir.runpytest("-s")

    result.assert_outcomes(passed=4)


def test_parametrize_with_regular_fixture(testdir):
    testdir.makepyfile(
        """
        import asyncio
        import logging
        import time

        import pytest


        @pytest.fixture
        def fixture_a():
            return "xxx"


        @pytest.mark.asyncio_cooperative
        @pytest.mark.parametrize("param", [1, 2])
        async def test_async_foo(fixture_a, param):
            await asyncio.sleep(param)
    """
    )
    result = testdir.runpytest("-s")
    result.assert_outcomes(passed=2)
