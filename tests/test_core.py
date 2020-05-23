def test_single(testdir):
    testdir.makeconftest("""""")

    testdir.makepyfile(
        """
        import asyncio
        import pytest


        @pytest.mark.asyncio_cooperative
        async def test_a():
            await asyncio.sleep(2)
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=1)


def test_double(testdir):
    testdir.makeconftest("""""")

    testdir.makepyfile(
        """
        import asyncio
        import pytest


        @pytest.mark.asyncio_cooperative
        async def test_a():
            await asyncio.sleep(2)


        @pytest.mark.asyncio_cooperative
        async def test_b():
            await asyncio.sleep(2)
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=2)
    assert result.duration < 4


def test_works_with_synchronous(testdir):
    testdir.makeconftest("""""")

    testdir.makepyfile(
        """
        import asyncio
        import pytest


        @pytest.mark.asyncio_cooperative
        async def test_a():
            await asyncio.sleep(2)


        def test_b():
            assert 1 == 1
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=2)
