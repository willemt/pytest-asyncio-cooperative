.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black

Use asyncio (cooperative multitasking) to run your I/O bound test suite efficiently and quickly.

.. code-block:: python
   :class: ignore
   
   import asyncio

   import pytest
   
   @pytest.mark.asyncio_cooperative
   async def test_a():
       await asyncio.sleep(2)
   
   
   @pytest.mark.asyncio_cooperative
   async def test_b():
       await asyncio.sleep(2)


.. code-block:: bash
   :class: ignore

   ========== 2 passed in 2.05 seconds ==========


Quickstart
----------
.. code-block:: bash
   :class: ignore

   pip install pytest-asyncio-cooperative


Compatibility
-------------
pytest-asyncio is NOT compatible with this plugin. Please uninstall pytest-asyncio or pass this flag to pytest `-p no:asyncio`

Fixtures
--------
It's recommended that async tests use async fixtures.

.. code-block:: bash
   :class: ignore

   import asyncio
   import pytest


   @pytest.fixture
   async def my_fixture():
       await asyncio.sleep(2)
       yield "XXX"
       await asyncio.sleep(2)


   @pytest.mark.asyncio_cooperative
   async def test_a(my_fixture):
       await asyncio.sleep(2)
       assert my_fixture == "XXX"


Goals
-----

- Reduce the total run time of I/O bound test suites via cooperative multitasking

- Reduce system resource usage via cooperative multitasking


Pros
----

- An I/O bound test suite will run faster (ie. individual tests will take just as long. The total runtime of the entire test suite will be faster)

- An I/O bound test suite will use less system resources (ie. only a single thread is used)

Cons
----

- Order of tests is not guaranteed (ie. some blocking operations might taken longer and affect the order of test results)

- Tests MUST be isolated from each other (ie. NO shared resources, NO `mock.patch`). However, note that locks can be used to ensure isolation.

- There is NO parallelism, CPU bound tests will NOT get a performance benefit


Mocks & Shared Resources
------------------------

When using mocks and shared resources cooperative multitasking means tests could have race conditions.

In this case you can use locks:

.. code-block:: bash
   :class: ignore

   import asyncio
   import pytest
   from pytest_asyncio_cooperative import Lock

   my_lock = Lock()

   @pytest.fixture(scope="function")
   async def lock():
       async with my_lock():
           yield

   @pytest.mark.asyncio_cooperative
   async def test_a(lock, mocker):
       await asyncio.sleep(2)
       mocker.patch("service.http.on_handler")
       access_shared_resource()
       assert my_fixture == "XXX"

   @pytest.mark.asyncio_cooperative
   async def test_b(lock, mocker):
       await asyncio.sleep(2)
       mocker.patch("service.http.on_handler")
       access_shared_resource()
       assert my_fixture == "XXX"

In the above example it's important to put the `lock` fixture on the far left-hand side to ensures mutual exclusivity.
