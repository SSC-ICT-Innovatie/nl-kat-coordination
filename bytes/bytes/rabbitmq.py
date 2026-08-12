import aio_pika
import structlog

from bytes.config import get_settings
from bytes.events.events import Event
from bytes.events.manager import EventManager

logger = structlog.get_logger(__name__)

_event_manager: EventManager | None = None


class RabbitMQEventManager(EventManager):
    def __init__(self, queue_uri: str):
        self.queue_uri = queue_uri
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None

    async def _get_channel(self) -> aio_pika.abc.AbstractChannel:
        if self._connection is None or self._connection.is_closed:
            self._connection = await aio_pika.connect_robust(self.queue_uri)
            self._channel = None
            logger.info("Connected to RabbitMQ")

        if self._channel is None or self._channel.is_closed:
            self._channel = await self._connection.channel()

        return self._channel

    async def publish(self, event: Event) -> None:
        event_data = event.model_dump_json()
        logger.debug("Publishing event: %s", event_data)
        queue_name = self._queue_name(event)

        channel = await self._get_channel()
        await channel.declare_queue(queue_name, durable=True)
        await channel.default_exchange.publish(aio_pika.Message(body=event_data.encode()), routing_key=queue_name)

        logger.info("Published event [event_id=%s] to queue %s", event.event_id, queue_name)

    @staticmethod
    def _queue_name(event: Event) -> str:
        return event.event_id


class NullManager(EventManager):
    async def publish(self, event: Event) -> None:
        pass


def create_event_manager() -> EventManager:
    global _event_manager

    if _event_manager is not None:
        return _event_manager

    settings = get_settings()

    if settings.queue_uri:
        _event_manager = RabbitMQEventManager(str(settings.queue_uri))
    else:
        _event_manager = NullManager()

    return _event_manager
