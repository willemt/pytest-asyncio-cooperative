def test_max_asyncio_tasks(pytester):
    pytester.makepyfile(
        """
        import asyncio

        import pytest

        # keeps track of all the tests currently executing
        concurrent = set()


        @pytest.mark.parametrize("x", range(4))
        @pytest.mark.asyncio_cooperative
        async def test_concurrent(x: int) -> None:
            concurrent.add(x)
            assert len(concurrent) <= 2

            await asyncio.sleep(1)

            concurrent.remove(x)
    """
    )

    result = pytester.runpytest("--max-asyncio-tasks=2")

    result.assert_outcomes(passed=4)
