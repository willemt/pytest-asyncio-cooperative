import pytest

from .conftest import includes_lines


def test_function_must_be_async(testdir):
    testdir.makeconftest("""""")

    testdir.makepyfile(
        """
        import asyncio
        import pytest


        @pytest.mark.asyncio_cooperative
        def test_a():
            assert 1 == 1
    """
    )

    expected_lines = [
        "E       Exception: Function test_a is not a coroutine.",
        "E       Tests with the `@pytest.mark.asyncio_cooperative` mark MUST be coroutines.",
        "E       Please add the `async` keyword to the test function.",
    ]

    result = testdir.runpytest()
    assert includes_lines(expected_lines, result.stdout.lines)

    result.assert_outcomes(failed=1)


@pytest.mark.parametrize("dur1, dur2, expectedfails, expectedpasses", [
    (1.1, 2, 2, 0),
    (2, 2, 2, 0),
])
def test_function_takes_too_long(testdir, dur1, dur2, expectedfails, expectedpasses):
    testdir.makeconftest(
        """""")

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
    """.format(dur1, dur2)
    )

    result = testdir.runpytest("--asyncio-task-timeout", "1")

    result.assert_outcomes(failed=expectedfails, passed=expectedpasses)
