import threading
import asyncio
import collections.abc
import functools
import inspect
import time
from sys import version_info as sys_version_info

import pytest

from _pytest.runner import call_and_report
from _pytest.skipping import Skip, evaluate_skip_marks

from .assertion import activate_assert_rewrite
from .fixtures import fill_fixtures


def pytest_addoption(parser):
    parser.addoption(
        "--max-asyncio-tasks",
        action="store",
        default=None,
        help="asyncio: maximum number of tasks to run concurrently (int)",
    )
    parser.addini(
        "max_asyncio_tasks",
        "asyncio: maximum number of tasks to run concurrently (int)",
        default=100,
    )

    parser.addoption(
        "--asyncio-task-timeout",
        action="store",
        default=None,
        help="asyncio: number of seconds before a test will be cancelled (int)",
    )
    parser.addini(
        "asyncio_task_timeout",
        "asyncio: number of seconds before a test will be cancelled (int)",
        default=600,
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
            call.duration = call.stop - call.start

    elif call.when == "setup":
        if hasattr(item, "start_setup") and hasattr(item, "stop_setup"):
            call.start = item.start_setup
            call.stop = item.stop_setup
            call.duration = call.stop - call.start

    elif call.when == "teardown":
        if hasattr(item, "start_teardown") and hasattr(item, "stop_teardown"):
            call.start = item.start_teardown
            call.stop = item.stop_teardown
            call.duration = call.stop - call.start


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
            if isinstance(teardown, collections.abc.Iterator):
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
        if inspect.iscoroutinefunction(item.function):
            await item.function(*fixture_values)
        else:
            item.function(*fixture_values)
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


def item_to_task(item):
    if getattr(item.function, "is_hypothesis_test", False):
        return hypothesis_test_wrapper(item)
    else:
        return test_wrapper(item)


def _run_test_loop(tasks, session, run_tests):
    max_tasks = int(
        session.config.getoption("--max-asyncio-tasks")
        or session.config.getini("max_asyncio_tasks")
    )

    loop = asyncio.new_event_loop()
    try:
        task = run_tests(tasks, int(max_tasks))
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
        markers = {m.name: m for m in item.own_markers}

        if "skip" in markers or "skipif" in markers:
            # Best to hand off to the core pytest logic to handle this so reporting works
            if isinstance(evaluate_skip_marks(item), Skip):
                regular_items.append(item)
                continue

        # Coerce into a task
        if "asyncio_cooperative" in markers:
            task = item_to_task(item)

            item._flakey = "flakey" in markers
            item_by_coro[task] = item
            tasks.append(task)
        else:
            regular_items.append(item)

    def get_coro(task):
        if sys_version_info >= (3, 8):
            return task.get_coro()
        else:
            return task._coro

    async def run_tests(tasks, max_tasks: int):
        sidelined_tasks = tasks[max_tasks:]
        tasks = tasks[:max_tasks]

        task_timeout = int(
            session.config.getoption("--asyncio-task-timeout")
            or session.config.getini("asyncio_task_timeout")
        )

        completed = []
        cancelled = []
        while tasks:
            # Schedule all the coroutines
            for i in range(len(tasks)):
                if asyncio.iscoroutine(tasks[i]):
                    tasks[i] = asyncio.create_task(tasks[i])

            # Mark when the task was started
            earliest_enqueue_time = time.time()
            for task in tasks:
                if isinstance(task, asyncio.Task):
                    item = item_by_coro[get_coro(task)]
                else:
                    item = item_by_coro[task]
                if not hasattr(item, "enqueue_time"):
                    item.enqueue_time = time.time()
                earliest_enqueue_time = min(item.enqueue_time, earliest_enqueue_time)

            time_to_wait = (time.time() - earliest_enqueue_time) - task_timeout
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED,
                timeout=min(30, int(time_to_wait)),
            )

            # Cancel tasks that have taken too long
            tasks = []
            for task in pending:
                now = time.time()
                item = item_by_coro[get_coro(task)]
                if task not in cancelled and task_timeout < now - item.enqueue_time:
                    if sys_version_info >= (3, 9):
                        msg = "Test took too long ({:.2f} s)".format(
                            now - item.enqueue_time
                        )
                        task.cancel(msg=msg)
                    else:
                        task.cancel()
                    cancelled.append(task)
                tasks.append(task)

            for result in done:
                item = item_by_coro[get_coro(result)]

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

                # We need to change .runtest to a synchronous function for pytest
                # however, if it is called again by retry libraries we need to rerun
                # the test instead of retuning the previous result
                def wrap_in_sync():
                    def sync_wrapper():
                        new_task = item_to_task(item)
                        
                        # We use a new thread because we can't block for an async function
                        # in the same thread as the current running event loop, nor
                        # we can nest event loops
                        result = None
                        def run_in_thread():
                            nonlocal result
                            try:
                                result = asyncio.run(new_task)
                            except Exception as e:
                                result = e
                        thread = threading.Thread(target=run_in_thread)
                        thread.start()
                        thread.join()

                        if isinstance(result, Exception):
                            raise result # type: ignore

                        return result

                    item.runtest = sync_wrapper

                    return result.result()

                item.runtest = wrap_in_sync

                item.ihook.pytest_runtest_protocol(item=item, nextitem=None)

                # Hack: See rewrite comment below
                # pytest_runttest_protocl will disable the rewrite assertion
                # so we renable it here
                activate_assert_rewrite(item)

                completed.append(result)

            if sidelined_tasks:
                if len(tasks) < max_tasks:
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
    if not previous_collectonly:
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
