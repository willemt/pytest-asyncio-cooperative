def test_autouse(pytester):
    pytester.makepyfile(
        """
        import pytest


        @pytest.fixture(autouse=True)
        async def side_effect_fixture(my_list):
            my_list[0] = "autouse fixture was here"


        @pytest.fixture()
        async def my_list():
            return [1,2,3]


        @pytest.mark.asyncio_cooperative
        async def test_autouse(my_list):
            assert my_list == ['autouse fixture was here', 2, 3]
    """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)
