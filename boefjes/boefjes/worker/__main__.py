import json
import logging.config
import os
from pathlib import Path

import click
import structlog

from .boefje_handler import LocalBoefjeHandler
from .client import BoefjeAPIClient
from .interfaces import WorkerManager
from .manager import SchedulerWorkerManager
from .oci_adapter import run_with_callback
from .repository import LocalPluginRepository

logging_format = os.getenv("LOGGING_FORMAT", "text")
log_cfg = Path(os.getenv("LOG_CFG", "logging.json"))

with log_cfg.open() as f:
    logging.config.dictConfig(json.load(f))

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper("iso", utc=False),
        (
            structlog.dev.ConsoleRenderer(colors=True, pad_level=False)
            if logging_format == "text"
            else structlog.processors.JSONRenderer()
        ),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@click.command()
@click.option("-p", "--plugins", type=str, default=None, multiple=True, help="A list of plugin ids to filter on.")
@click.option(
    "-l", "--log-level", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]), help="Log level", default="INFO"
)
@click.argument("input_url", default="")
def cli(plugins: tuple[str] | None, log_level: str, input_url: str) -> None:
    logger.setLevel(log_level)
    logger.info("Starting runtime")

    if input_url:
        return run_with_callback(input_url)

    base_url = os.getenv("BOEFJES_API")
    oci_image = os.getenv("OCI_IMAGE")

    if not plugins:
        env_plugins = os.getenv("PLUGINS")
        parsed_plugins = env_plugins.split(",") if env_plugins else None
    else:
        parsed_plugins = list(plugins)

    pool_size = int(os.getenv("POOL_SIZE", "2"))
    poll_interval = float(os.getenv("POLL_INTERVAL", "10.0"))
    heartbeat = float(os.getenv("WORKER_HEARTBEAT", "1.0"))
    deduplicate = bool(os.getenv("DEDUPLICATE", "false"))

    if base_url is None:
        raise ValueError("An task API is needed for a worker setup. See the BOEFJE_API environment variable.")

    if oci_image is None:
        raise ValueError(
            "This environment has not been built properly: no OCI_IMAGE environment variable found. "
            "Please build the boefje image with this variable set to the oci image id."
        )

    outgoing_request_timeout = int(os.getenv("OUTGOING_REQUEST_TIMEOUT", "30"))

    boefje_api = BoefjeAPIClient(base_url, outgoing_request_timeout, [oci_image], parsed_plugins)
    handler = LocalBoefjeHandler(LocalPluginRepository(Path()), boefje_api)
    logger.info(
        "Configured BoefjeAPI [base_url=%s, outgoing_request_timeout=%s, images=%s, plugins=%s]",
        base_url,
        outgoing_request_timeout,
        [oci_image],
        parsed_plugins,
    )

    SchedulerWorkerManager(handler, boefje_api, pool_size, poll_interval, heartbeat, deduplicate).run(
        WorkerManager.Queue.BOEFJES
    )


if __name__ == "__main__":
    cli()
