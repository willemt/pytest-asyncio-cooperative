def test_max_asyncio_tasks(pytester):
    pytester.makepyfile(
        """
        import asyncio

        import pytest

        # keeps track of all the tests currently executing
        concurrent = set()


        @pytest.mark.parametrize("x", range(4))
        @pytest.mark.asyncio_cooperative
        async def test_concurrent(x: int) -> None:
            concurrent.add(x)
            assert len(concurrent) <= 2

            await asyncio.sleep(1)

            concurrent.remove(x)
    """
    )

    result = pytester.runpytest("--max-asyncio-tasks=2")

    result.assert_outcomes(passed=4)


def test_max_asyncio_tasks_by_mark(pytester):
    pytester.makeini(
        """
        [pytest]
        markers =
            foo
            bar
            baz
        """
    )

    pytester.makepyfile(
        """
        import asyncio

        import pytest

        # keeps track of all the tests currently executing
        class Concurrent:
            def __init__(self):
                self.total = 0
                self.foo = 0
                self.bar = 0
                self.baz = 0


        concurrent = Concurrent()


        @pytest.mark.parametrize("x", range(10))
        @pytest.mark.asyncio_cooperative
        @pytest.mark.foo
        async def test_concurrent_mark_foo(x: int) -> None:
            concurrent.total += 1
            concurrent.foo += 1

            assert concurrent.total <= 4
            assert concurrent.foo <= 1

            await asyncio.sleep(0.1)

            concurrent.total -= 1
            concurrent.foo -=1


        @pytest.mark.parametrize("x", range(10))
        @pytest.mark.asyncio_cooperative
        @pytest.mark.bar
        async def test_concurrent_mark_bar(x: int) -> None:
            concurrent.total += 1
            concurrent.bar += 1

            assert concurrent.total <= 4
            assert concurrent.bar <= 2

            await asyncio.sleep(0.1)

            concurrent.total -= 1
            concurrent.bar -=1


        @pytest.mark.parametrize("x", range(10))
        @pytest.mark.asyncio_cooperative
        @pytest.mark.baz
        async def test_concurrent_mark_baz(x: int) -> None:
            concurrent.total += 1
            concurrent.baz += 1

            assert concurrent.total <= 4
            assert concurrent.baz <= 3

            await asyncio.sleep(0.1)

            concurrent.total -= 1
            concurrent.baz -=1
    """
    )

    result = pytester.runpytest(
        "--max-asyncio-tasks=4", "--max-asyncio-tasks-by-mark", "foo=1 bar=2 baz=3"
    )

    result.assert_outcomes(passed=30)


def test_max_asyncio_tasks_by_mark_multiple(pytester):
    """
    At most 2 tasks can be executed, because `test_concurrent_mark_foo_bar`
    uses both `foo` and `bar` marks.
    """

    pytester.makeini(
        """
        [pytest]
        markers =
            foo
            bar
        """
    )

    pytester.makepyfile(
        """
        import asyncio

        import pytest

        # keeps track of all the tests currently executing
        class Concurrent:
            def __init__(self):
                self.total = 0


        concurrent = Concurrent()


        @pytest.mark.parametrize("x", range(10))
        @pytest.mark.asyncio_cooperative
        @pytest.mark.foo
        @pytest.mark.bar
        async def test_concurrent_mark_foo_bar(x: int) -> None:
            concurrent.total += 1

            assert concurrent.total <= 2

            await asyncio.sleep(0.1)

            concurrent.total -= 1


        @pytest.mark.parametrize("x", range(10))
        @pytest.mark.asyncio_cooperative
        @pytest.mark.bar
        async def test_concurrent_mark_bar(x: int) -> None:
            concurrent.total += 1

            assert concurrent.total <= 2

            await asyncio.sleep(0.1)

            concurrent.total -= 1
    """
    )

    result = pytester.runpytest(
        "--max-asyncio-tasks=4", "--max-asyncio-tasks-by-mark", "foo=1 bar=2"
    )

    result.assert_outcomes(passed=20)


def test_max_asyncio_tasks_by_mark_remainder(pytester):
    pytester.makeini(
        """
        [pytest]
        markers =
            foo
        """
    )

    pytester.makepyfile(
        """
        import asyncio

        import pytest

        # keeps track of all the tests currently executing
        class Concurrent:
            def __init__(self):
                self.foo = 0
                self.remainder = 0
                self.max_remainder = 0


        concurrent = Concurrent()


        @pytest.mark.parametrize("x", range(10))
        @pytest.mark.asyncio_cooperative
        @pytest.mark.foo
        async def test_concurrent_mark_foo(x: int) -> None:
            concurrent.foo += 1
            assert concurrent.foo <= 1
            await asyncio.sleep(0.1)
            concurrent.foo -= 1


        @pytest.mark.parametrize("x", range(10))
        @pytest.mark.asyncio_cooperative
        async def test_concurrent_mark_remainder(x: int) -> None:
            concurrent.remainder += 1
            concurrent.max_remainder = max(concurrent.remainder, concurrent.max_remainder) 
            assert concurrent.remainder <= 2
            await asyncio.sleep(0.1)
            concurrent.remainder -= 1

            # The last test to run
            if x == 9:
                assert concurrent.max_remainder == 2

    """
    )

    result = pytester.runpytest(
        "--max-asyncio-tasks=10",
        "--max-asyncio-tasks-by-mark=foo=1",
        "--max-asyncio-tasks-by-mark-remainder=2",
    )

    result.assert_outcomes(passed=20)


def test_max_asyncio_tasks_by_mark_groups(pytester):
    pytester.makeini(
        """
        [pytest]
        markers =
            foo
            bar
        """
    )

    pytester.makepyfile(
        """
        import asyncio

        import pytest

        # keeps track of all the tests currently executing
        class Concurrent:
            def __init__(self):
                self.total = 0
                self.foo = 0
                self.bar = 0
                self.foo_bar = 0
                self.max_foo_bar = 0


        concurrent = Concurrent()


        @pytest.mark.parametrize("x", range(10))
        @pytest.mark.foo
        @pytest.mark.asyncio_cooperative
        async def test_concurrent_mark_foo(x: int) -> None:
            concurrent.total += 1
            concurrent.foo += 1

            assert concurrent.total <= 2
            assert concurrent.foo <= 2

            await asyncio.sleep(0.1)

            concurrent.total -= 1
            concurrent.foo -= 1


        @pytest.mark.parametrize("x", range(10))
        @pytest.mark.bar
        @pytest.mark.asyncio_cooperative
        async def test_concurrent_mark_bar(x: int) -> None:
            concurrent.total += 1
            concurrent.bar += 1

            assert concurrent.total <= 2
            assert concurrent.bar <= 2

            await asyncio.sleep(0.1)

            concurrent.total -= 1
            concurrent.bar -= 1


        @pytest.mark.parametrize("x", range(10))
        @pytest.mark.foo
        @pytest.mark.bar
        @pytest.mark.asyncio_cooperative
        async def test_concurrent_mark_foo_bar(x: int) -> None:
            concurrent.total += 1
            concurrent.foo_bar += 1

            assert concurrent.total <= 2
            assert concurrent.foo_bar <= 2

            concurrent.max_foo_bar = max(concurrent.foo_bar, concurrent.max_foo_bar) 

            await asyncio.sleep(0.1)

            concurrent.total -= 1
            concurrent.foo_bar -= 1

            # Make sure the scheduler is not overcounting when a test has multiple marks
            # matching the group. In such a case, only 1 active item should be counted
            # for the group, and so 2 concurrent tasks should run.
            if x == 9:
                assert concurrent.max_foo_bar == 2
    """
    )

    result = pytester.runpytest(
        "--max-asyncio-tasks=10",
        "--max-asyncio-tasks-by-mark=foo,bar=2",
    )

    result.assert_outcomes(passed=30)
