def test_synchronous_tests_do_not_run_if_async_tests_fail(testdir):
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

    result = testdir.runpytest()

    result.assert_outcomes(failed=1)

    # we expect this:
    # result.assert_outcomes(failed=1, passed=1)
