import asyncio

import pytest


@pytest.mark.asyncio_cooperative
async def test_a():
    await asyncio.sleep(2)


@pytest.mark.asyncio_cooperative
async def test_b():
    await asyncio.sleep(2)
