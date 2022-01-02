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


def test_class_based_tests_with_fixture(testdir):
    testdir.makepyfile("""
        import pytest


        class TestSuite:
            @pytest.fixture
            async def test_fixture(self):
                return "test_fixture"

            @pytest.mark.asyncio_cooperative
            async def test_cooperative(self, test_fixture):
                assert test_fixture == "test_fixture"

    """)

    result = testdir.runpytest()

    result.assert_outcomes(passed=1)
