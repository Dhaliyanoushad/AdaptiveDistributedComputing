"""Run ASGI tests without network sockets, including in restricted Windows sandboxes.

This test-only event loop polls callbacks instead of using a socketpair wakeup.
It supports the in-process ASGI/thread tests, not network servers or clients.
Normal unittest discovery remains the preferred command on an unrestricted PC.
"""

import asyncio
from pathlib import Path
import selectors
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class PollingSelector(selectors.SelectSelector):
    def select(self, timeout=None):
        delay = 0.001 if timeout is None else min(timeout, 0.001)
        if not self.get_map():
            time.sleep(delay)
            return []
        return super().select(delay)


class InProcessLoop(asyncio.SelectorEventLoop):
    def __init__(self):
        super().__init__(PollingSelector())

    def _make_self_pipe(self):
        self._ssock = self._csock = None

    def _close_self_pipe(self):
        pass


class InProcessPolicy(asyncio.DefaultEventLoopPolicy):
    def new_event_loop(self):
        return InProcessLoop()


if __name__ == '__main__':
    asyncio.set_event_loop_policy(InProcessPolicy())
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern='test_master*.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
