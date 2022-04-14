def test_skip(testdir):
    testdir.makeconftest("""""")

    testdir.makepyfile(
        """
        import asyncio
        import pytest


        @pytest.mark.skip(reason="for test")
        @pytest.mark.asyncio_cooperative
        async def test_a():
            await asyncio.sleep(2)
    """
    )

    result = testdir.runpytest()
    # FIXME: should be skipped=1
    result.assert_outcomes(errors=0, failed=0, passed=0, xfailed=0, xpassed=0, skipped=0)


def test_skipif(testdir):
    testdir.makeconftest("""""")

    testdir.makepyfile(
        """
        import asyncio
        import sys
        import pytest


        @pytest.mark.skipif(sys.version_info < (9, 0), reason="too old")
        @pytest.mark.asyncio_cooperative
        async def test_a():
            await asyncio.sleep(2)
    """
    )

    result = testdir.runpytest()
    result.assert_outcomes(errors=0, failed=0, passed=0, xfailed=0, xpassed=0, skipped=1)
