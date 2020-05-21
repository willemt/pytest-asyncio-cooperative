import asyncio

import pytest

runs = 0


@pytest.mark.flakey
@pytest.mark.asyncio_cooperative
async def test_a():
    global runs
    await asyncio.sleep(2)
    if runs == 0:
        runs += 1
        raise Exception


@pytest.mark.asyncio_cooperative
async def test_b():
    await asyncio.sleep(2)
