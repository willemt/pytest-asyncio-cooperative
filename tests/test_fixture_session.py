def test_session_fixture_with_exception(testdir):
    testdir.makepyfile(
        """
        import asyncio

        import pytest


        class Foo:
            def reset(self):
                print("Foo reset")


        @pytest.fixture(scope="session")
        def session():
            raise NotImplementedError("xxx")
            foo = Foo()
            yield foo


        @pytest.fixture
        def regularfixture(session):
            session.reset()
            yield session


        @pytest.mark.asyncio_cooperative
        async def test_1(regularfixture):
            await asyncio.sleep(1)

    """
    )

    result = testdir.runpytest("-q")

    assert "object has no attribute 'reset'" not in "".join(result.outlines)

    result.assert_outcomes(passed=0, failed=0, errors=1)
