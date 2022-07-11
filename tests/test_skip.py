def test_skipx(testdir):
    testdir.makeconftest("""""")

    testdir.makepyfile(
        """
        import asyncio
        import pytest


        @pytest.mark.skip(reason="for test")
        @pytest.mark.asyncio_cooperative
        async def test_a():
            raise Exception("should not be run!")
    """
    )

    result = testdir.runpytest()
    # FIXME: should be skipped=1
    result.assert_outcomes(errors=0, failed=0, passed=0, xfailed=0, xpassed=0, skipped=1)


def test_skipif_is_true(testdir):
    testdir.makeconftest("""""")

    testdir.makepyfile(
        """
        import asyncio
        import sys
        import pytest


        @pytest.mark.skipif(sys.version_info < (99999999, 0), reason="too old")
        @pytest.mark.asyncio_cooperative
        async def test_a():
            raise Exception("should not be run!")
    """
    )

    result = testdir.runpytest()
    result.assert_outcomes(errors=0, failed=0, passed=0, xfailed=0, xpassed=0, skipped=1)


def test_skipif_is_false(testdir):
    testdir.makeconftest("""""")

    testdir.makepyfile(
        """
        import asyncio
        import sys
        import pytest


        @pytest.mark.skipif(sys.version_info < (0, 0), reason="too old")
        @pytest.mark.asyncio_cooperative
        async def test_a():
            await asyncio.sleep(0.1)
    """
    )

    result = testdir.runpytest()
    result.assert_outcomes(errors=0, failed=0, passed=1, xfailed=0, xpassed=0, skipped=0)


def test_skipif_with_passing(testdir):
    testdir.makeconftest("""""")

    testdir.makepyfile(
        """
        import pytest
        SKIPPING = True


        @pytest.mark.asyncio_cooperative
        @pytest.mark.skip(reason="because reasons")
        async def test_1():
            assert True


        @pytest.mark.asyncio_cooperative
        @pytest.mark.skipif(SKIPPING, reason="because we need to skip")
        async def test_2():
            assert False


        @pytest.mark.asyncio_cooperative
        async def test_3():
            assert True
    """
    )

    result = testdir.runpytest()
    result.assert_outcomes(errors=0, failed=0, passed=1, xfailed=0, xpassed=0, skipped=2)
