def test_parameterize_single(testdir):
    testdir.makeconftest("""""")

    testdir.makepyfile(
        """
        import asyncio
        import pytest


        @pytest.mark.asyncio_cooperative
        @pytest.mark.parametrize("number", [1, 2, 3])
        async def test_a(number):
            print(number, flush=True)
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
            print(number, flush=True)
            await asyncio.sleep(2)


        @pytest.mark.asyncio_cooperative
        async def test_b():
            await asyncio.sleep(2)
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=4)
