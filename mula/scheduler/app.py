import os
import threading

import structlog
from opentelemetry import trace

from scheduler import context, schedulers, server
from scheduler.utils import thread

tracer = trace.get_tracer(__name__)


class App:
    """Main application definition for the scheduler implementation of KAT.

    The App is responsible for starting and managing:

        * Schedulers: The schedulers are responsible for managing the queues
        and tasks for a specific organisation.

        * Server: The server is responsible for exposing the application
        through a REST API.

        * Metrics: The collection of application specific metrics.
    """

    def __init__(self, ctx: context.AppContext) -> None:
        """Initialize the application.

        Args:
            ctx (context.AppContext): Application context of shared data (e.g.
                configuration, external services connections).
        """

        self.logger: structlog.BoundLogger = structlog.getLogger(__name__)
        self.ctx: context.AppContext = ctx
        self.server: server.Server | None = None

        threading.excepthook = self._unhandled_exception
        self.stop_event: threading.Event = threading.Event()
        self.lock: threading.Lock = threading.Lock()

        self.schedulers: dict[
            str,
            schedulers.Scheduler
            | schedulers.BoefjeScheduler
            | schedulers.NormalizerScheduler
            | schedulers.ReportScheduler,
        ] = {}

    def run(self) -> None:
        """Start the main scheduler application, and run in threads the
        following processes:

            * schedulers
            * metrics collecting
            * api server
        """
        self.start_schedulers()
        self.start_server(self.schedulers)

        if self.ctx.config.collect_metrics:
            self.start_collectors()

        # Main thread
        while not self.stop_event.is_set():
            self.stop_event.wait()

        # When the stop event is set, we want to gracefully shutdown the
        # rest of the application.
        self.shutdown()

        # We're calling this here, because we want to issue a shutdown from
        # within a thread, otherwise it will not exit a docker container.
        # Source: https://stackoverflow.com/a/1489838/1346257
        os._exit(1)

    def start_schedulers(self) -> None:
        boefje = schedulers.BoefjeScheduler(ctx=self.ctx)
        self.schedulers[boefje.scheduler_id] = boefje

        normalizer = schedulers.NormalizerScheduler(ctx=self.ctx)
        self.schedulers[normalizer.scheduler_id] = normalizer

        report = schedulers.ReportScheduler(ctx=self.ctx)
        self.schedulers[report.scheduler_id] = report

        for s in self.schedulers.values():
            s.run()

    def start_server(
        self,
        schedulers: dict[
            str,
            schedulers.Scheduler
            | schedulers.BoefjeScheduler
            | schedulers.NormalizerScheduler
            | schedulers.ReportScheduler,
        ],
    ) -> None:
        self.server = server.Server(self.ctx, schedulers)
        thread.ThreadRunner(name="App-server", target=self.server.run, stop_event=self.stop_event, loop=False).start()

    def start_collectors(self) -> None:
        thread.ThreadRunner(
            name="App-metrics_collector", target=self._collect_metrics, stop_event=self.stop_event, interval=10
        ).start()

    def shutdown(self) -> None:
        """Shutdown the scheduler application, and all threads."""
        self.logger.info("Shutdown initiated")

        self.stop_event.set()

        # Stop all schedulers
        for s in self.schedulers.values():
            s.stop()

        # Stop all threads that are still running, except the main thread.
        # These threads likely have a blocking call and as such are not able
        # to leverage a stop event.
        self._stop_threads()

        self.logger.info("Shutdown complete")

    def _stop_threads(self) -> None:
        """Stop all threads, except the main thread."""
        for t in threading.enumerate():
            if t is threading.current_thread():
                continue

            if t is threading.main_thread():
                continue

            if not t.is_alive():
                continue

            t.join(5)

    def _unhandled_exception(self, args: threading.ExceptHookArgs) -> None:
        """Gracefully shutdown the scheduler application, and all threads
        when a unhandled exception occurs.
        """
        self.logger.error("Unhandled exception occurred: %s", args.exc_value)
        self.stop_event.set()

    def _collect_metrics(self) -> None:
        """Collect application metrics throughout the application."""
        for s in self.schedulers.values():
            qsize = self.ctx.datastores.pq_store.qsize(s.scheduler_id)
            self.ctx.metrics_qsize.labels(scheduler_id=s.scheduler_id).set(qsize)

            status_counts = self.ctx.datastores.task_store.get_status_counts(s.scheduler_id)
            for status, count in status_counts.items():
                self.ctx.metrics_task_status_counts.labels(scheduler_id=s.scheduler_id, status=status).set(count)
