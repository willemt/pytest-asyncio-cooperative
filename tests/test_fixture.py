def test_function_fixture(testdir):
    testdir.makepyfile(
        """
        import asyncio
        import uuid
        import pytest

        @pytest.fixture
        async def grandparent_fixture():
            return str(uuid.uuid4())


        @pytest.fixture
        async def my_fixture(grandparent_fixture):
            return grandparent_fixture


        @pytest.mark.asyncio_cooperative
        async def test_a(my_fixture, grandparent_fixture):
            assert my_fixture == grandparent_fixture
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=1)


def test_function_fixture_is_unique_for_function(testdir):
    testdir.makepyfile(
        """
        import asyncio
        import uuid
        import pytest

        global_uuid = None

        @pytest.fixture
        async def grandparent_fixture():
            return str(uuid.uuid4())


        @pytest.fixture
        async def my_fixture(grandparent_fixture):
            return grandparent_fixture


        @pytest.mark.asyncio_cooperative
        async def test_a(my_fixture, grandparent_fixture):
            global global_uuid
            global_uuid = my_fixture
            assert my_fixture == grandparent_fixture


        @pytest.mark.asyncio_cooperative
        async def test_b(my_fixture, grandparent_fixture):
            await asyncio.sleep(2)
            assert global_uuid
            assert not global_uuid == my_fixture
            assert my_fixture == grandparent_fixture

    """
    )
    result = testdir.runpytest()
    result.assert_outcomes(passed=2)


def test_request(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.asyncio_cooperative
        async def test_a(request):
            assert request is not None
    """
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_tmp_path(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.asyncio_cooperative
        async def test_a(tmp_path):
            assert isinstance(str(tmp_path), str)
    """
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_indirect(testdir):
    testdir.makepyfile(
        """
        import asyncio
        import pytest
        @pytest.fixture
        def to_str(request):
            yield str(request.param)
        

        @pytest.mark.asyncio_cooperative
        @pytest.mark.parametrize("to_str, expected", [(1, "1"), (2, "2"), (3, "3")], indirect=[
        "to_str"])
        async def test_a(to_str, expected):
            await asyncio.sleep(2)
            assert to_str == expected
    """
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=3)


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


def test_session_fixture(testdir):
    testdir.makepyfile(
        """
        import asyncio
        import pytest

        counter = 0

        @pytest.fixture(scope="session")
        async def grandparent_fixture():
            await asyncio.sleep(1)
            global counter
            counter += 1
            yield counter
            await asyncio.sleep(1)


        @pytest.fixture
        async def my_fixture(grandparent_fixture):
            await asyncio.sleep(1)
            yield "XXX"
            await asyncio.sleep(1)


        @pytest.mark.asyncio_cooperative
        async def test_a(my_fixture):
            await asyncio.sleep(1)


        @pytest.mark.asyncio_cooperative
        async def test_b(my_fixture, grandparent_fixture):
            assert grandparent_fixture == 1
            await asyncio.sleep(1)
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
