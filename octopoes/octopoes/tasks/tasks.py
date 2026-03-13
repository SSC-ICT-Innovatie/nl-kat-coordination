from logging import config
from pathlib import Path

import structlog
import yaml
from pydantic import TypeAdapter

from octopoes.config.settings import QUEUE_NAME_OCTOPOES, Settings
from octopoes.core.app import get_octopoes
from octopoes.events.events import DBEvent, DBEventType
from octopoes.tasks.app import app

settings = Settings()
logger = structlog.get_logger(__name__)

try:
    with Path(settings.log_cfg).open() as log_config:
        config.dictConfig(yaml.safe_load(log_config))
        logger.info("Configured loggers with config: %s", settings.log_cfg)
except FileNotFoundError:
    logger.warning("No log config found at: %s", settings.log_cfg)

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper("iso", utc=False),
        (
            structlog.dev.ConsoleRenderer(
                colors=True, pad_level=False, exception_formatter=structlog.dev.plain_traceback
            )
            if settings.logging_format == "text"
            else structlog.processors.JSONRenderer()
        ),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


@app.task(queue=QUEUE_NAME_OCTOPOES, ignore_result=True)
def handle_event(event: dict) -> None:
    try:
        parsed_event: DBEvent = TypeAdapter(DBEventType).validate_python(event)
        octopoes = get_octopoes(parsed_event.client)
        octopoes.process_event(parsed_event)
        octopoes.commit()
    except Exception:
        logger.exception("Failed to handle event: %s", event)
        raise
