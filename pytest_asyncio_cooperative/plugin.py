import asyncio
import functools
import inspect
import time

import pytest

from _pytest.runner import call_and_report

from .assertion import activate_assert_rewrite
from .fixtures import fill_fixtures


def pytest_addoption(parser):
    parser.addoption(
        "--max-asyncio-tasks",
        action="store",
        default=100,
        help="asyncio: maximum number of tasks to run concurrently (int)",
    )
    parser.addoption(
        "--asyncio-task-timeout",
        action="store",
        default=120,
        help="asyncio: number of seconds before a test will be cancelled (int)",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "asyncio_cooperative: run an async test cooperatively with other async tests.",
    )
    config.addinivalue_line(
        "markers", "flakey: if this test fails then run it one more time."
    )


@pytest.hookspec
def pytest_runtest_makereport(item, call):
    # Tests are run outside of the normal place, so we have to inject our timings

    if call.when == "call":
        if hasattr(item, "start") and hasattr(item, "stop"):
            call.start = item.start
            call.stop = item.stop

    elif call.when == "setup":
        if hasattr(item, "start_setup") and hasattr(item, "stop_setup"):
            call.start = item.start_setup
            call.stop = item.stop_setup

    elif call.when == "teardown":
        if hasattr(item, "start_teardown") and hasattr(item, "stop_teardown"):
            call.start = item.start_teardown
            call.stop = item.stop_teardown


def not_coroutine_failure(function_name: str, *args, **kwargs):
    raise Exception(
        f"Function {function_name} is not a coroutine.\n"
        f"Tests with the `@pytest.mark.asyncio_cooperative` mark MUST be coroutines.\n"
        f"Please add the `async` keyword to the test function."
    )


async def test_wrapper(item):
    # Do setup
    item.start_setup = time.time()
    fixture_values, teardowns = await fill_fixtures(item)
    item.stop_setup = time.time()

    # This is a class method test so prepend `self`
    if item.instance:
        fixture_values.insert(0, item.instance)

    async def do_teardowns():
        item.start_teardown = time.time()
        for teardown in teardowns:
            if inspect.isgenerator(teardown):
                try:
                    teardown.__next__()
                except StopIteration:
                    pass
            else:
                try:
                    await teardown.__anext__()
                except StopAsyncIteration:
                    pass
        item.stop_teardown = time.time()

    # Run test
    item.start = time.time()
    try:
        await item.function(*fixture_values)
    except:
        # Teardown here otherwise we might leave fixtures with locks acquired
        item.stop = time.time()
        await do_teardowns()
        raise

    item.stop = time.time()
    await do_teardowns()


# TODO: move to hypothesis module
async def hypothesis_test_wrapper(item):
    """
    Hypothesis is synchronous, let's run inside an executor to keep asynchronicity
    """

    # Do setup
    item.start_setup = time.time()
    fixture_values, teardowns = await fill_fixtures(item)
    item.stop_setup = time.time()

    default_loop = asyncio.get_running_loop()
    inner_test = item.function.hypothesis.inner_test

    def async_to_sync(*args, **kwargs):
        # FIXME: can we cache this loop across multiple runs?
        loop = asyncio.new_event_loop()
        task = inner_test(*args, **kwargs)
        try:
            loop.run_until_complete(task)
        finally:
            loop.close()

    # Run test
    item.function.hypothesis.inner_test = async_to_sync
    wrapped_func_with_fixtures = functools.partial(item.function, *fixture_values)
    await default_loop.run_in_executor(None, wrapped_func_with_fixtures)

    # Do teardowns
    item.start_teardown = time.time()
    for teardown in teardowns:
        try:
            await teardown.__anext__()
        except StopAsyncIteration:
            pass
    item.stop_teardown = time.time()


class NotCoroutine(Exception):
    pass


def item_to_task(item):
    if inspect.iscoroutinefunction(item.function):
        return test_wrapper(item)
    elif getattr(item.function, "is_hypothesis_test", False):
        return hypothesis_test_wrapper(item)
    else:
        raise NotCoroutine


def _run_test_loop(tasks, session, run_tests):
    loop = asyncio.new_event_loop()
    try:
        task = run_tests(tasks, int(session.config.getoption("--max-asyncio-tasks")))
        loop.run_until_complete(task)
    finally:
        loop.close()


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtestloop(session):
    if session.config.pluginmanager.is_registered("asyncio"):
        raise Exception(
            "pytest-asyncio-cooperative is NOT compatible with pytest-asyncio\n"
            "Uninstall pytest-asyncio or pass this option to pytest: `-p no:asyncio`\n"
        )

    # pytest-cooperative needs to hijack the runtestloop from pytest.
    # To prevent the default pytest runtestloop from running tests we make it think we
    # were only collecting tests. Slightly a hack, but it is needed for other plugins
    # which use the pytest_runtestloop hook.
    previous_collectonly = session.config.option.collectonly
    session.config.option.collectonly = True
    yield
    session.config.option.collectonly = previous_collectonly

    session.wrapped_fixtures = {}

    flakes_to_retry = []

    # Collect our coroutines
    regular_items = []
    item_by_coro = {}
    tasks = []
    for item in session.items:
        markers = [m.name for m in item.own_markers]

        if "skip" in markers:
            continue

        # Coerce into a task
        if "asyncio_cooperative" in markers:
            try:
                task = item_to_task(item)
            except NotCoroutine:
                item.runtest = functools.partial(not_coroutine_failure, item.name)
                item.ihook.pytest_runtest_protocol(item=item, nextitem=None)
                continue

            item._flakey = "flakey" in markers
            item_by_coro[task] = item
            tasks.append(task)
        else:
            regular_items.append(item)

    async def run_tests(tasks, max_tasks):
        sidelined_tasks = tasks[max_tasks:]
        tasks = tasks[:max_tasks]

        task_timeout = int(session.config.getoption("--asyncio-task-timeout"))

        completed = []
        while tasks:

            # Mark when the task was started
            for task in tasks:
                if isinstance(task, asyncio.Task):
                    item = item_by_coro[task._coro]
                else:
                    item = item_by_coro[task]
                if not hasattr(item, "enqueue_time"):
                    item.enqueue_time = time.time()

            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED, timeout=30
            )

            # Cancel tasks that have taken too long
            tasks = []
            for task in pending:
                now = time.time()
                item = item_by_coro[task._coro]
                if task_timeout < now - item.enqueue_time:
                    task.cancel()
                tasks.append(task)

            for result in done:
                item = item_by_coro[result._coro]

                # Flakey tests will be run again if they failed
                # TODO: add retry count
                if item._flakey:
                    try:
                        result.result()
                    except:
                        item._flakey = None
                        new_task = item_to_task(item)
                        flakes_to_retry.append(new_task)
                        item_by_coro[new_task] = item
                        continue

                item.runtest = lambda: result.result()

                item.ihook.pytest_runtest_protocol(item=item, nextitem=None)

                # Hack: See rewrite comment below
                # pytest_runttest_protocl will disable the rewrite assertion
                # so we renable it here
                activate_assert_rewrite(item)

                completed.append(result)

            if sidelined_tasks:
                tasks.append(sidelined_tasks.pop(0))

        return completed

    # Do assert rewrite
    # Hack: pytest's implementation sets up assert rewriting as a shared
    # resource. This causes a race condition between async tests. Therefore we
    # need to activate the assert rewriting here
    if tasks:
        item = item_by_coro[tasks[0]]
        activate_assert_rewrite(item)

    # Run the tests using cooperative multitasking
    _run_test_loop(tasks, session, run_tests)

    # Run failed flakey tests
    if flakes_to_retry:
        _run_test_loop(flakes_to_retry, session, run_tests)

    # Run synchronous tests
    session.items = regular_items
    for i, item in enumerate(session.items):
        nextitem = session.items[i + 1] if i + 1 < len(session.items) else None
        item.config.hook.pytest_runtest_protocol(item=item, nextitem=nextitem)
        if session.shouldfail:
            raise session.Failed(session.shouldfail)
        if session.shouldstop:
            raise session.Interrupted(session.shouldstop)

    return True
