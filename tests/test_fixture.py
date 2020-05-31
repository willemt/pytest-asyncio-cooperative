def test_fixtures(testdir):
    testdir.makeconftest("""""")

    testdir.makepyfile(
        """
        import asyncio
        import pytest


        @pytest.fixture
        async def grandparent_fixture():
            await asyncio.sleep(2)
            yield "YYY"
            await asyncio.sleep(2)


        @pytest.fixture
        async def my_fixture(grandparent_fixture):
            await asyncio.sleep(2)
            yield "XXX"
            await asyncio.sleep(2)


        @pytest.mark.asyncio_cooperative
        async def test_a(my_fixture):
            await asyncio.sleep(2)


        @pytest.mark.asyncio_cooperative
        async def test_b(my_fixture, grandparent_fixture):
            await asyncio.sleep(2)
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=2)


def test_synchronous_generator_fixture(testdir):
    testdir.makepyfile(
        """
        import asyncio
        import pytest


        @pytest.fixture
        def my_fixture():
            yield "YYY"


        @pytest.mark.asyncio_cooperative
        async def test_a(my_fixture):
            await asyncio.sleep(2)
            assert my_fixture == "YYY"
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=1)


def test_synchronous_generator_fixture_with_parent(testdir):
    testdir.makepyfile(
        """
        import asyncio
        import pytest

        @pytest.fixture
        def grandparent_fixture():
            yield "YYY"


        @pytest.fixture
        def my_fixture(grandparent_fixture):
            yield "XXX"


        @pytest.mark.asyncio_cooperative
        async def test_a(my_fixture):
            await asyncio.sleep(2)
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=1)


def test_synchronous_fixture_with_parent(testdir):
    testdir.makepyfile(
        """
        import asyncio
        import pytest

        @pytest.fixture
        def grandparent_fixture():
            return "YYY"


        @pytest.fixture
        def my_fixture(grandparent_fixture):
            return "XXX"


        @pytest.mark.asyncio_cooperative
        async def test_a(my_fixture):
            await asyncio.sleep(2)
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=1)



def test_synchronous_fixture(testdir):
    testdir.makepyfile(
        """
        import asyncio
        import pytest


        @pytest.fixture
        def my_fixture():
            return "YYY"


        @pytest.mark.asyncio_cooperative
        async def test_a(my_fixture):
            await asyncio.sleep(2)
            assert my_fixture == "YYY"
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=1)


def test_prefer_user_fixture_over_plugin_fixture(testdir):
    testdir.makepyfile(
        """
        import asyncio
        import pytest


        @pytest.fixture
        def cache():
            yield "YYY"


        @pytest.mark.asyncio_cooperative
        async def test_a(cache):
            await asyncio.sleep(2)
            assert cache == "YYY"
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=1)
