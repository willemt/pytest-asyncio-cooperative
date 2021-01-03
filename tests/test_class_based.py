def test_class_based_tests(testdir):
    testdir.makepyfile("""
        import pytest


        class TestSuite:
            @pytest.mark.asyncio_cooperative
            async def test_cooperative(self):
                assert True

    """)

    result = testdir.runpytest()

    result.assert_outcomes(passed=1)
