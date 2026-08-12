import json
from datetime import datetime

import pytest

from bytes.events.events import RawFileReceived
from bytes.rabbitmq import RabbitMQEventManager
from tests.loading import get_raw_data_meta


@pytest.mark.anyio
async def test_event_published_successfully(event_manager: RabbitMQEventManager) -> None:
    test_organization = "test"
    raw_data_meta = get_raw_data_meta()

    # We use an isolated queue this way to not conflict with other integration tests
    raw_data_meta.boefje_meta.organization = test_organization

    event = RawFileReceived(
        created_at=datetime(2000, 10, 10, 10), organization=test_organization, raw_data=raw_data_meta
    )
    await event_manager.publish(event)

    channel = await event_manager._get_channel()
    queue = await channel.declare_queue(event_manager._queue_name(event), durable=True)
    message = await queue.get()

    assert message is not None
    response = json.loads(message.body)
    await message.ack()

    assert response["organization"] == test_organization
    assert response["raw_data"] == event.raw_data.model_dump(mode="json")
    assert response["created_at"] == "2000-10-10T10:00:00"
