import pytest


@pytest.mark.parametrize(
    "dur1, dur2, expectedfails, expectedpasses",
    [
        (1.1, 2, 2, 0),
        (2, 2, 2, 0),
    ],
)
def test_function_takes_too_long(testdir, dur1, dur2, expectedfails, expectedpasses):
    testdir.makeconftest("""""")

    testdir.makepyfile(
        """
        import asyncio
        import pytest


        @pytest.mark.asyncio_cooperative
        async def test_a():
            await asyncio.sleep({})
        
        @pytest.mark.asyncio_cooperative
        async def test_b():
            await asyncio.sleep({})
    """.format(
            dur1, dur2
        )
    )

    result = testdir.runpytest("--asyncio-task-timeout", "1")

    result.assert_outcomes(failed=expectedfails, passed=expectedpasses)
