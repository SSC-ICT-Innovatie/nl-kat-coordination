from logging import config
from pathlib import Path

import structlog
import yaml
from celery.utils.log import get_task_logger
from pydantic import TypeAdapter

from octopoes.config.settings import QUEUE_NAME_OCTOPOES, Settings
from octopoes.core.app import get_xtdb_client
from octopoes.events.events import DBEvent, DBEventType
from octopoes.tasks.app import app
from octopoes.xtdb.client import XTDBSession

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

from celery.utils.log import get_task_logger
task_logger = get_task_logger(__name__)

@app.task(queue=QUEUE_NAME_OCTOPOES, ignore_result=True)
def handle_event(event: dict) -> None:
    task_logger.warning("ENTER task: %s", event.get("id"))
    try:
        parsed_event: DBEvent = TypeAdapter(DBEventType).validate_python(event)

        session = XTDBSession(get_xtdb_client(str(settings.xtdb_uri), parsed_event.client))
        octopoes = get_octopoes(settings, parsed_event.client, session)
        octopoes.process_event(parsed_event)
        session.commit()
    except Exception:
        logger.exception("Failed to handle event: %s", event)
        raise
