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
        "--max-asyncio-tasks-by-mark",
        action="store",
        default=None,
        help="asyncio: maximum number of tasks to run concurrently for each mark (mark1,mark2,..=int pairs, space separated)",
    )
    parser.addini(
        "max_asyncio_tasks_by_mark",
        "asyncio: asyncio: maximum number of tasks to run concurrently for each mark (mark1,mark2,..=int pairs, space separated)",
        default=None,
    )

    parser.addoption(
        "--max-asyncio-tasks-by-mark-remainder",
        action="store",
        default=0,
        help="asyncio: maximum number of tasks to run concurrently for tasks that didn't match any "
        "marks in `--max-asyncio-tasks-by-mark` (default 0, unlimited)",
    )
    parser.addini(
        "max_asyncio_tasks_by_mark_remainder",
        help="asyncio: maximum number of tasks to run concurrently for tasks that didn't match any "
        "marks in `--max-asyncio-tasks-by-mark` (default 0, unlimited)",
        default=0,
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
        default=120,
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


class MarkLimits:
    # To support multiple marks in the same group separate by comma, a shared group object
    # is created and inserted into the groups dictionary multiple times for each mark in
    # the group. When a test has multiple marks that belong to the same group, each mark
    # will be added multiple times to the set, but the result will be that the number
    # of active items in the group will only increase by 1. A simple ref count is not enough
    # in this situation, because it would overcount how many items are actively running.
    class Group:
        def __init__(self, max):
            self.max = max
            self.items = set()

    def __init__(self):
        self.groups = {}
        self.remainder = 0
        self.remainder_max = 0

    def update_config(self, session):
        if session.config.getoption("--max-asyncio-tasks-by-mark"):
            self.groups = MarkLimits.parse_max_tasks_by_mark(
                session.config.getoption("--max-asyncio-tasks-by-mark"),
                "--max-asyncio-tasks-by-mark",
            )
        else:
            self.groups = MarkLimits.parse_max_tasks_by_mark(
                session.config.getini("max_asyncio_tasks_by_mark"),
                "max_asyncio_tasks_by_mark",
            )

        self.remainder_max = int(
            session.config.getoption("--max-asyncio-tasks-by-mark-remainder")
            or session.config.getini("max_asyncio_tasks_by_mark_remainder")
        )

    @staticmethod
    def parse_max_tasks_by_mark(config_value, debug_prefix):
        if not config_value:
            return {}

        result = {}
        pairs = config_value.split()
        for pair in pairs:
            columns = pair.split("=")
            if len(columns) > 2:
                assert False, f"`{debug_prefix}`: too many `=` in `{pair}`"

            try:
                max_tasks = int(columns[1])
            except ValueError:
                assert False, f"`{debug_prefix}`: expected integer in `{pair}`"

            group = MarkLimits.Group(max_tasks)
            for mark in columns[0].split(","):
                assert (
                    mark not in result
                ), f"`{debug_prefix}`: multiple occurences of mark `{mark}`"
                result[mark] = group

        return result

    def would_exceed_max_marks(self, item):
        for mark in item.own_markers:
            group = self.groups.get(mark.name)
            if group and len(group.items) >= group.max:
                return True

        if self.remainder_max and self.remainder >= self.remainder_max:
            return True

        return False

    def update_active_marks(self, item, add):
        matched_mark = False

        for mark in item.own_markers:
            group = self.groups.get(mark.name)
            if group:
                # Not returning here, because each mark must be accounted for,
                # not just the first matching one.
                matched_mark = True
                if add:
                    group.items.add(item)
                elif item in group.items:
                    group.items.remove(item)

        # Make sure not to overcount the remainder
        if matched_mark:
            return

        if self.remainder_max:
            if add:
                self.remainder += 1
            else:
                self.remainder -= 1


def get_coro(task):
    if sys_version_info >= (3, 8):
        return task.get_coro()
    else:
        return task._coro


def get_item_by_coro(task, item_by_coro):
    if isinstance(task, asyncio.Task):
        return item_by_coro[get_coro(task)]
    else:
        return item_by_coro[task]


def _run_test_loop(tasks, session, run_tests):
    max_tasks = int(
        session.config.getoption("--max-asyncio-tasks")
        or session.config.getini("max_asyncio_tasks")
    )

    mark_limits = MarkLimits()
    mark_limits.update_config(session)

    loop = asyncio.new_event_loop()
    try:
        task = run_tests(tasks, int(max_tasks), mark_limits)
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

    async def run_tests(tasks, max_tasks: int, mark_limits):
        sidelined_tasks = tasks
        tasks = []

        def enqueue_tasks():
            while len(tasks) < max_tasks:
                remove_index = None

                for index, task in enumerate(sidelined_tasks):
                    item = get_item_by_coro(task, item_by_coro)
                    if not mark_limits.would_exceed_max_marks(item):
                        mark_limits.update_active_marks(item, add=True)
                        tasks.append(task)
                        remove_index = index
                        break

                if remove_index == None:
                    # No available tasks were found, give up control.
                    break

                # Removing element from start/middle of the list is actually
                # quite fast compared to iterating to the end of the list in
                # the above loop.
                sidelined_tasks.pop(remove_index)

        enqueue_tasks()

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
                item = get_item_by_coro(task, item_by_coro)
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
                mark_limits.update_active_marks(item, add=False)

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

            enqueue_tasks()

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
