import asyncio

import pytest


@pytest.fixture(scope="module")
async def preparation():
    await asyncio.sleep(1)
    yield "something"
    await asyncio.sleep(1)


@pytest.mark.asyncio_cooperative
async def test_a(preparation):
    await asyncio.sleep(2)


@pytest.mark.asyncio_cooperative
async def test_b(preparation):
    await asyncio.sleep(2)
