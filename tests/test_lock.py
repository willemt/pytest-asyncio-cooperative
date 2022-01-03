def test_lock(testdir):
    testdir.makeconftest("""""")

    testdir.makepyfile(
        """
        import asyncio
        import pytest

        class Lock:
            def __call__(self):
                try:
                    return self.lock
                except AttributeError:
                    self.lock = asyncio.Lock()
                    return self.lock


        lock = Lock()

        @pytest.fixture(scope="function")
        async def the_lock():
            async with lock():
                yield


        @pytest.mark.asyncio_cooperative
        async def test_a(the_lock):
            await asyncio.sleep(2)
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=1)


def test_lock_with_failure(testdir):
    testdir.makeconftest("""""")

    testdir.makepyfile(
        """
        import asyncio
        import pytest


        class Lock:
            def __call__(self):
                try:
                    return self.lock
                except AttributeError:
                    self.lock = asyncio.Lock()
                    return self.lock


        lock = Lock()


        @pytest.fixture(scope="function")
        async def the_lock():
            async with lock():
                yield


        @pytest.mark.asyncio_cooperative
        async def test_a(the_lock):
            await asyncio.sleep(1)
            raise Exception
            await asyncio.sleep(1)


        @pytest.mark.asyncio_cooperative
        async def test_b(the_lock):
            await asyncio.sleep(2)
    """
    )

    result = testdir.runpytest()

    result.assert_outcomes(passed=1, failed=1)
