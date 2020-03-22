import asyncio

import pytest


@pytest.mark.asyncio_cooperative
async def test_a():
    await asyncio.sleep(2)


@pytest.mark.asyncio_cooperative
async def test_b():
    await asyncio.sleep(2)


# Regular synchronous test which get's tested outside of the async event loop
def test_c():
    assert 1 == 1
