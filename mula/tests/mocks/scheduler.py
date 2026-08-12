import time

from scheduler import schedulers

from tests.utils import functions

from . import listener


class MockScheduler(schedulers.Scheduler):
    ITEM_TYPE = functions.TestModel

    def run(self) -> None:
        # Listener
        self.listeners["mock-listener"] = listener.MockListener()

        self.run_in_thread(name="mock-listener", target=self.listeners["mock-listener"].listen, loop=True)

        # Thread
        self.run_in_thread(name="mock-scheduler", target=self._run, loop=True)

    def _run(self) -> None:
        time.sleep(1)
