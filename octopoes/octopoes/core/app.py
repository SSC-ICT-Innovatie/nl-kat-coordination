from typing import Any

import structlog
from amqp import AMQPError

from octopoes.config.settings import GATHER_BIT_METRICS, QUEUE_NAME_OCTOPOES, Settings
from octopoes.core.service import OctopoesService
from octopoes.events.manager import EventManager, get_rabbit_channel
from octopoes.tasks.app import app as celery_app
from octopoes.xtdb.client import XTDBHTTPClient, XTDBSession

logger = structlog.get_logger(__name__)
settings = Settings()


def get_xtdb_client(base_uri: str, client: str) -> XTDBHTTPClient:
    base_uri = base_uri.rstrip("/")

    return XTDBHTTPClient(f"{base_uri}/_xtdb", node=client)


def close_rabbit_channel(queue_uri: str) -> None:
    rabbit_channel = get_rabbit_channel(queue_uri)

    try:
        rabbit_channel.connection.close()
        logger.info("Closed connection to RabbitMQ")
    except AMQPError:
        logger.exception("Unable to close rabbit")


_octopoes_instances: dict[str, Any] = {}


def get_octopoes(client: str) -> OctopoesService:
    if client not in _octopoes_instances:
        _octopoes_instances[client] = bootstrap_octopoes(client=client)
    return _octopoes_instances[client]


def bootstrap_octopoes(client: str, xtdb_session: XTDBSession | None = None) -> OctopoesService:
    if not xtdb_session:
        xtdb_session = XTDBSession(get_xtdb_client(str(settings.xtdb_uri), client))
    event_manager = EventManager(client, str(settings.queue_uri), celery_app, QUEUE_NAME_OCTOPOES)
    return OctopoesService(event_manager, xtdb_session, GATHER_BIT_METRICS)
