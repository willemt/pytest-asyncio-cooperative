import asyncio

import pytest


@pytest.mark.skip(reason="WIP")
@pytest.mark.asyncio_cooperative
async def test_a():
    await asyncio.sleep(2)
    raise Exception


@pytest.mark.asyncio_cooperative
async def test_b():
    await asyncio.sleep(2)
