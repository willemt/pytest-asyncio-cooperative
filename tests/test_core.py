def test_one_test(testdir):
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


def test_two_tests(testdir):
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


def test_plays_nicely_with_synchronous_test(testdir):
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


def test_synchronous_tests_run_if_async_tests_fail(testdir):
    testdir.makeconftest("""""")

    testdir.makepyfile(
        """
        import asyncio
        import pytest


        @pytest.mark.asyncio_cooperative
        async def test_a():
            assert False


        def test_b():
            assert 1 == 1
    """
    )

    result = testdir.runpytest("-s")

    # we expect this:
    result.assert_outcomes(failed=1, passed=1)
