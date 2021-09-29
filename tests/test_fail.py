from typing import List


def includes_lines(expected_lines: List[str], lines: List[str]) -> bool:
    for line in lines:
        for i, eline in enumerate(list(expected_lines)):
            if eline == line:
                expected_lines.pop(i)
                break

    assert expected_lines == []
    return expected_lines == []


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

def test_function_takes_too_long(testdir):
    testdir.makeconftest(
        """""")

    testdir.makepyfile(
        """
        import asyncio
        import pytest


        @pytest.mark.asyncio_cooperative
        async def test_a():
            await asyncio.sleep(2)
        
        @pytest.mark.asyncio_cooperative
        async def test_b():
            await asyncio.sleep(1.1)
    """
    )

    result = testdir.runpytest("--asyncio-task-timeout", "1")

    result.assert_outcomes(failed=1, passed=1)
