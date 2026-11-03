import threading
from collections.abc import Callable
from typing import Any

import structlog


class ThreadRunner(threading.Thread):
    """ThreadRunner extends threading.Thread to allow for graceful shutdown
    using event signalling. Additionally to the standard threading.Thread
    attributes we use the following attributes.

    Attributes:
        logger:
            The logger for the class.
        stop_event:
            A threading.Event object used for signalling thread stop events.
        interval:
            A float describing the time between loop iterations.
        exception:
            A python Exception that can be set in order to signify that
            an exception has occurred during the execution of the thread.
        _target:
            A callable that is executed when the thread is started.
        loop:
            A boolean describing whether the thread should run in a loop.
    """

    def __init__(
        self,
        name: str,
        target: Callable[[], Any],
        stop_event: threading.Event,
        callback: Callable[[], Any] | None = None,
        callback_args: tuple | None = None,
        interval: float | None = None,
        daemon: bool = False,
        loop: bool = True,
    ) -> None:
        """Initialize the ThreadRunner

        Args:
            name: A string describing the name of the thread.
            target: A callable that is executed when the thread is started.
            stop_event: A threading.Event object used for signalling thread
            interval: A float describing the time between loop iterations.
            daemon: A boolean describing whether the thread should be a daemon
            loop: A boolean describing whether the thread should run in a loop.
        """
        self.logger: structlog.BoundLogger = structlog.getLogger(__name__)
        self._target: Callable[[], Any] = target
        self.stop_event: threading.Event = stop_event
        self.interval: float | None = interval
        self.loop: bool = loop
        self.exception: Exception | None = None
        self.callback: Callable[[], Any] | None = callback
        self.callback_args: tuple[Any, ...] = callback_args or ()

        super().__init__(target=self._target, daemon=daemon)

        self.name = name if name else self.name

    def run_forever(self) -> None:
        """Run the target function in a loop until the stop event is set."""
        while not self.stop_event.is_set():
            try:
                self._target()
                self.stop_event.wait(self.interval)
            except Exception as exc:
                self.exception = exc
                self.logger.exception("Exception in thread: %s", self.name, exc_info=exc)
                self.stop_event.set()
                raise exc

        if self.callback:
            self.callback(*self.callback_args)

    def run_once(self) -> None:
        """Run the target function once."""
        try:
            self._target()
        except Exception as exc:
            self.exception = exc
            self.logger.exception("Exception in thread: %s", self.name, exc_info=exc)
            self.stop_event.set()
            raise exc

        if self.callback:
            self.callback(*self.callback_args)

    def run(self) -> None:
        self.logger.debug("Starting thread: %s", self.name, thread_name=self.name)
        if self.loop:
            self.run_forever()
        else:
            self.run_once()

        self.logger.debug("Thread stopped: %s", self.name)

    def join(self, timeout: float | None = None) -> None:
        self.logger.debug("Stopping thread: %s", self.name, thread_name=self.name)

        self.stop_event.set()
        super().join(timeout)

        self.logger.debug("Thread stopped: %s", self.name, thread_name=self.name)

    def stop(self) -> None:
        self.stop_event.set()
