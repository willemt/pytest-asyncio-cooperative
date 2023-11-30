from typing import Optional, Tuple

from _pytest.fixtures import FixtureDef
from _pytest.fixtures import SubRequest
from _pytest.main import Session
from _pytest.nodes import Item
from _pytest.runner import call_and_report

import apluggy as pluggy


hookspec = pluggy.HookspecMarker('pytest-asyncio-cooperative')


@hookspec(firstresult=True)
async def pytest_runtestloop(session: "Session") -> Optional[object]:
    ...


@hookspec(firstresult=True)
async def pytest_runtest_protocol(
    item: "Item", nextitem: "Optional[Item]"
) -> Optional[object]:
    ...


@hookspec
async def pytest_runtest_logstart(
    nodeid: str, location: Tuple[str, Optional[int], str]
) -> None:
    ...


@hookspec
async def pytest_runtest_logfinish(
    nodeid: str, location: Tuple[str, Optional[int], str]
) -> None:
    ...


@hookspec
async def pytest_runtest_setup(item: "Item") -> None:
    ...


@hookspec
async def pytest_runtest_call(item: "Item") -> None:
    ...


@hookspec
async def pytest_runtest_teardown(item: "Item", nextitem: Optional["Item"]) -> None:
    ...


# -------------------------------------------------------------------------
# Fixture related hooks
# -------------------------------------------------------------------------


@hookspec(firstresult=True)
async def pytest_fixture_setup(
    fixturedef: "FixtureDef[Any]", request: "SubRequest"
) -> Optional[object]:
    ...


def pytest_fixture_post_finalizer(
    fixturedef: "FixtureDef[Any]", request: "SubRequest"
) -> None:
    ...
