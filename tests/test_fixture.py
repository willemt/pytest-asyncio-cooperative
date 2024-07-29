import pytest


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


def test_ordering_of_fixtures_based_off_function_arguments(testdir):
    testdir.makepyfile(
        """
        import asyncio
        import pytest

        @pytest.fixture
        async def abc():
            await asyncio.sleep(0.1)
            yield "abc"
            await asyncio.sleep(0.1)


        @pytest.fixture
        async def _def():
            await asyncio.sleep(0.1)
            yield "def"
            await asyncio.sleep(0.1)


        @pytest.fixture
        async def ghi():
            await asyncio.sleep(0.1)
            yield "ghi"
            await asyncio.sleep(0.1)


        @pytest.mark.asyncio_cooperative
        async def test_ordering(ghi, _def, abc):
            assert ghi == "ghi"
            assert abc == "abc"
            assert _def == "def"
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=1)


def test_ordering_of_fixtures_based_off_function_arguments_with_session_fixture(
    testdir,
):
    testdir.makepyfile(
        """
        import asyncio
        import pytest

        @pytest.fixture(scope="session")
        async def abc():
            await asyncio.sleep(0.1)
            yield "abc"
            await asyncio.sleep(0.1)


        @pytest.fixture
        async def _def():
            await asyncio.sleep(0.1)
            yield "def"
            await asyncio.sleep(0.1)


        @pytest.fixture
        async def ghi():
            await asyncio.sleep(0.1)
            yield "ghi"
            await asyncio.sleep(0.1)


        @pytest.mark.asyncio_cooperative
        async def test_ordering(ghi, _def, abc):
            assert ghi == "ghi"
            assert abc == "abc"
            assert _def == "def"
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=1)


def test_fixture_cleanup(testdir):
    testdir.makepyfile(
        """
        import asyncio
        import pytest

        @pytest.fixture
        async def abc():
            await asyncio.sleep(0.1)
            yield {}
            try:
                # we need to do cleanup here, but the current task has been cancelled
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                raise RuntimeError("we shouldn't have been cancelled")

        @pytest.mark.asyncio_cooperative
        async def test_concurrent(abc) -> None:
            await asyncio.sleep(5)
    """
    )

    result = testdir.runpytest("--asyncio-task-timeout=2")
    assert "we shouldn't have been cancelled" not in result.stdout.str()


def test_concurrent_function_fixture_filling(testdir):
    testdir.makepyfile(
        """
        import asyncio
        import uuid
        import pytest

        @pytest.fixture
        async def aaa():
            await asyncio.sleep(2)


        @pytest.fixture
        async def bbb():
            await asyncio.sleep(2)


        @pytest.mark.asyncio_cooperative
        async def test_a(aaa, bbb):
            assert True
    """
    )

    result = testdir.runpytest("--asyncio-task-timeout=3")

    result.assert_outcomes(passed=1)


@pytest.mark.parametrize("scope", ["module", "session"])
@pytest.mark.parametrize("def_", ["def", "async def"])
@pytest.mark.parametrize("ret", ["return", "yield"])
@pytest.mark.parametrize("fail", [False, True])
def test_shared_fixture_caching(testdir, scope, def_, ret, fail):
    testdir.makepyfile(
        f"""
        import pytest
        import time

        called = False
        @pytest.fixture(scope="{scope}")
        {def_} shared_fixture():
            global called
            if called:
                assert {fail}
            else:
                called = True
                assert not {fail}
            {ret}

        @pytest.mark.asyncio_cooperative
        async def test_a(shared_fixture):
            assert True

        @pytest.mark.asyncio_cooperative
        async def test_b(shared_fixture):
            assert True
    """
    )

    result = testdir.runpytest()

    if fail:
        result.assert_outcomes(failed=2)
        # Should be errors instead of failures
        # https://github.com/willemt/pytest-asyncio-cooperative/issues/42
    else:
        result.assert_outcomes(passed=2)


def test_getting_fixture_from_closest_conftest(testdir):
    testdir.makepyfile(
        **{
            "conftest": """
           import pytest

           @pytest.fixture
           def some_fixture():
               return "foo"
            """,
            "bar/conftest": """
            import pytest

           @pytest.fixture
           def some_fixture():
               return "bar"
            """,
            "test_foo": """
            import pytest

            @pytest.mark.asyncio_cooperative
            def test_foo(some_fixture):
                assert some_fixture == "foo"
            """,
            "bar/test_bar": """
            import pytest

            @pytest.mark.asyncio_cooperative
            def test_bar(some_fixture):
                assert some_fixture == "bar"
            """,
        }
    )
    result = testdir.runpytest()
    result.assert_outcomes(passed=2)


def test_fixture_nested_exception(testdir):
    testdir.makepyfile(
        f"""
        import pytest


        @pytest.fixture(scope="module")
        async def first():
            return "first"


        @pytest.fixture(scope="module")
        async def second(first):
            assert False
            yield first


        @pytest.mark.asyncio_cooperative
        async def test_hello(second):
            print("hello")
        """
    )

    result = testdir.runpytest()
    result.assert_outcomes(errors=0, failed=1)
