def test_cached_function_can_handle_kwargs(testdir):
    testdir.makepyfile(
        """
        import pytest


        @pytest.mark.asyncio_cooperative
        async def test_a(pytestconfig):
            pass


        def test_b(pytestconfig):
            pass

    """
    )
    result = testdir.runpytest()
    result.assert_outcomes(passed=2)
