import re


def test_timing_in_junitxml(pytester):
    pytester.makeconftest("""""")

    pytester.makepyfile(
        """
        import asyncio
        import pytest


        @pytest.mark.asyncio_cooperative
        async def test_a():
            await asyncio.sleep(1)
    """
    )

    result = pytester.runpytest("--junitxml=junit.xml")

    result.assert_outcomes(passed=1)

    found = False
    with (pytester.path / "junit.xml").open() as f:
        for match in re.finditer(r'time="([\d.]+)"', f.read()):
            assert float(match[1]) > 0.7
            found = True
    assert found
