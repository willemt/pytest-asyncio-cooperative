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
