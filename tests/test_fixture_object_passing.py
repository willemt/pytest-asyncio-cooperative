def test_objects_passed_with_function_scope(testdir):
    testdir.makepyfile(
        """
        import pytest


        @pytest.fixture
        def outer():
            print("outer: setup")
            yield object()
            print("outer: cleanup")


        @pytest.fixture
        def middle(outer):
            print("middle: setup")
            yield outer, object()
            print("middle: cleanup")


        @pytest.fixture
        def inner(middle, outer):
            print("inner: setup")
            yield outer, middle, object()
            print("inner: cleanup")


        @pytest.mark.asyncio_cooperative
        async def test_async(inner, middle, outer) -> None:
            assert inner[0] is outer
            assert middle[0] is outer
            assert inner[1][1] is middle[1]
    """
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=1)
