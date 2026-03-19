import json
import logging.config
from pathlib import Path
from types import SimpleNamespace

import structlog
from prometheus_client import CollectorRegistry, Gauge, Info

import scheduler
from scheduler import clients, storage
from scheduler.config import settings
from scheduler.storage import stores
from scheduler.utils import remove_trailing_slash


class AppContext:
    """AppContext allows shared data between modules.

    Attributes:
        config:
            A settings.Settings object containing configurable application
            settings
        services:
            A dict containing all the external services connectors that
            are used and need to be shared in the scheduler application.
        task_store:
            A stores.TaskStore object used for storing tasks.
        pq_store:
            A stores.PriorityQueueStore object used for storing priority queues.
        metrics_registry:
            A prometheus_client.CollectorRegistry object used for storing metrics.
        metrics_qsize:
            A prometheus_client.Gauge object used for storing the queue size of
            the schedulers.
    """

    metrics_qsize: Gauge
    metrics_task_status_counts: Gauge

    def __init__(self) -> None:
        """Initializer of the AppContext class."""
        self.config: settings.Settings = settings.Settings()

        # Load logging configuration
        with Path(self.config.log_cfg).open("rt", encoding="utf-8") as f:
            logging.config.dictConfig(json.load(f))

        # Check if we enabled structured logging in the configuration
        if self.config.logging_format == "json":
            structlog.configure(
                processors=[
                    # If log level is too low, abort pipeline and throw away log entry.
                    structlog.stdlib.filter_by_level,
                    # Add the name of the logger to event dict.
                    structlog.stdlib.add_logger_name,
                    # Add log level to event dict.
                    structlog.stdlib.add_log_level,
                    # Perform %-style formatting.
                    structlog.stdlib.PositionalArgumentsFormatter(),
                    # Add a timestamp in ISO 8601 format.
                    structlog.processors.TimeStamper(fmt="iso", utc=False),
                    # If the "stack_info" key in the event dict is true, remove it
                    # and render the current stack trace in the "stack" key.
                    structlog.processors.StackInfoRenderer(),
                    # If the "exc_info" key in the event dict is either true or a
                    # sys.exc_info() tuple, remove "exc_info" and render the
                    # exception with traceback into the "exception" key.
                    structlog.processors.format_exc_info,
                    # If some value is in bytes, decode it to a Unicode str.
                    structlog.processors.UnicodeDecoder(),
                    # Add callsite parameters.
                    structlog.processors.CallsiteParameterAdder(
                        {
                            structlog.processors.CallsiteParameter.FILENAME,
                            structlog.processors.CallsiteParameter.FUNC_NAME,
                            structlog.processors.CallsiteParameter.LINENO,
                        }
                    ),
                    # Render the final event dict as JSON.
                    structlog.processors.JSONRenderer(),
                ],
                context_class=dict,
                # `logger_factory` is used to create wrapped loggers that are used
                # for OUTPUT. This one returns a `logging.Logger`. The final value
                # (a JSON string) from the final processor (`JSONRenderer`) will
                # be passed to the method of the same name as that you've called on
                # the bound logger.
                logger_factory=structlog.stdlib.LoggerFactory(),
                # `wrapper_class` is the bound logger that you get back from
                # get_logger(). This one imitates the API of `logging.Logger`.
                wrapper_class=structlog.stdlib.BoundLogger,
                # Effectively freeze configuration after creating the first bound
                # logger.
                cache_logger_on_first_use=True,
            )
        else:
            structlog.configure(
                processors=[
                    structlog.contextvars.merge_contextvars,
                    structlog.processors.add_log_level,
                    structlog.processors.StackInfoRenderer(),
                    structlog.dev.set_exc_info,
                    structlog.stdlib.PositionalArgumentsFormatter(),
                    structlog.processors.TimeStamper("iso", utc=False),
                    structlog.dev.ConsoleRenderer(pad_level=False, exception_formatter=structlog.dev.plain_traceback),
                ],
                context_class=dict,
                # `logger_factory` is used to create wrapped loggers that are used
                # for OUTPUT. This one returns a `logging.Logger`.
                logger_factory=structlog.stdlib.LoggerFactory(),
                # `wrapper_class` is the bound logger that you get back from
                # get_logger(). This one imitates the API of `logging.Logger`.
                wrapper_class=structlog.stdlib.BoundLogger,
                # Effectively freeze configuration after creating the first bound
                # logger.
                cache_logger_on_first_use=True,
            )

        self.logger: structlog.BoundLogger = structlog.get_logger(__name__)

        # Set the logging level
        if self.config.debug:
            self.logger.setLevel(logging.DEBUG)

        # Services
        katalogus_service = clients.Katalogus(
            host=remove_trailing_slash(str(self.config.host_katalogus)),
            source=f"scheduler/{scheduler.__version__}",
            timeout=self.config.katalogus_request_timeout,
            pool_connections=self.config.katalogus_pool_connections,
        )

        bytes_service = clients.Bytes(
            host=remove_trailing_slash(str(self.config.host_bytes)),
            source=f"scheduler/{scheduler.__version__}",
            user=self.config.host_bytes_user,
            password=self.config.host_bytes_password,
            timeout=self.config.bytes_request_timeout,
            pool_connections=self.config.bytes_pool_connections,
        )

        octopoes_service = clients.Octopoes(
            host=remove_trailing_slash(str(self.config.host_octopoes)),
            source=f"scheduler/{scheduler.__version__}",
            timeout=self.config.octopoes_request_timeout,
            pool_connections=self.config.octopoes_pool_connections,
            orgs=katalogus_service.get_organisations(),
        )

        # Register external services, SimpleNamespace allows us to use dot
        # notation
        self.services: SimpleNamespace = SimpleNamespace(
            **{
                clients.Katalogus.name: katalogus_service,
                clients.Octopoes.name: octopoes_service,
                clients.Bytes.name: bytes_service,
            }
        )

        # Database connection
        try:
            dbconn = storage.DBConn(dsn=str(self.config.db_uri), pool_size=self.config.db_connection_pool_size)
            dbconn.connect()
        except storage.errors.StorageError:
            self.logger.exception("Failed to connect to database")
            raise
        except Exception:
            self.logger.exception("Failed to connect to database")
            raise

        # Datastores, SimpleNamespace allows us to use dot notation
        self.datastores: SimpleNamespace = SimpleNamespace(
            **{
                stores.ScheduleStore.name: stores.ScheduleStore(dbconn),
                stores.TaskStore.name: stores.TaskStore(dbconn),
                stores.PriorityQueueStore.name: stores.PriorityQueueStore(dbconn),
            }
        )

        # Metrics collector registry
        self.metrics_registry: CollectorRegistry = CollectorRegistry()

        Info(
            name="app_settings", documentation="Scheduler configuration settings", registry=self.metrics_registry
        ).info(
            {
                "pq_maxsize": str(self.config.pq_maxsize),
                "pq_grace_period": str(self.config.pq_grace_period),
                "pq_max_random_objects": str(self.config.pq_max_random_objects),
                "monitor_organisations_interval": str(self.config.monitor_organisations_interval),
            }
        )

        self.metrics_qsize = Gauge(
            name="scheduler_qsize",
            documentation="Size of the scheduler queue",
            registry=self.metrics_registry,
            labelnames=["scheduler_id"],
        )

        self.metrics_task_status_counts = Gauge(
            name="scheduler_task_status_counts",
            documentation="Number of tasks in each status",
            registry=self.metrics_registry,
            labelnames=["scheduler_id", "status"],
        )
