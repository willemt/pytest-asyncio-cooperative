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

- All tests MUST be coroutines (ie. have the `async` keyword)

- Order of tests is not guaranteed (ie. some blocking operations might taken longer and affect the order of test results)

- Tests MUST be isolated from each other (ie. NO shared resources, NO `mock.patch`)

- There is NO parallelism, CPU bound tests will NOT get a performance benefit
