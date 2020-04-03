import asyncio
import datetime

from hypothesis import given, settings
from hypothesis import strategies as st

import pytest


@pytest.fixture
async def my_fixture():
    await asyncio.sleep(2)
    yield "1234"
    await asyncio.sleep(2)


@pytest.mark.asyncio_cooperative
@settings(deadline=datetime.timedelta(minutes=1))
@given(st.text())
async def test_a(my_fixture, data):
    print("test_a")
    await asyncio.sleep(0.5)


@pytest.mark.asyncio_cooperative
async def test_b(my_fixture):
    await asyncio.sleep(1)
    print("test_b")
    await asyncio.sleep(1)
    print("test_b")
    await asyncio.sleep(1)
    print("test_b")
    await asyncio.sleep(1)
