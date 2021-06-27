import asyncio


class Lock:
    def __call__(self):
        try:
            return self.lock
        except AttributeError:
            self.lock = asyncio.Lock()
            return self.lock
