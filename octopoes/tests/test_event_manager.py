import json
import uuid
from datetime import datetime
from unittest import mock

import pika

from octopoes.events.events import OOIDBEvent, OperationType, ScanProfileDBEvent
from octopoes.events.manager import EventManager


def test_event_manager_create_ooi(mocker, network):
    celery_mock = mocker.Mock()
    channel_mock = mocker.Mock()

    mocker.patch.object(uuid, "uuid4", return_value="1754a4c8-f0b8-42c8-b294-5706ce23a47d")
    manager = EventManager("test", "amqp://test-queue-uri", celery_mock, "queue", lambda x: channel_mock)
    event = OOIDBEvent(
        operation_type=OperationType.CREATE, valid_time=datetime(2023, 1, 1), new_data=network, client="test"
    )
    manager.publish(event)

    celery_mock.send_task.assert_called_once_with(
        "octopoes.tasks.tasks.handle_event",
        (
            {
                "entity_type": "ooi",
                "operation_type": "create",
                "valid_time": "2023-01-01T00:00:00",
                "client": "test",
                "old_data": None,
                "new_data": {
                    "object_type": "Network",
                    "scan_profile": None,
                    "primary_key": "Network|internet",
                    "name": "internet",
                    "user_id": None,
                },
            },
        ),
        queue="queue",
        task_id="1754a4c8-f0b8-42c8-b294-5706ce23a47d",
    )

    channel_mock.basic_publish.assert_not_called()


def test_event_manager_create_empty_scan_profile(mocker, empty_scan_profile):
    celery_mock = mocker.Mock()
    channel_mock = mocker.Mock()

    mocker.patch.object(uuid, "uuid4", return_value="1754a4c8-f0b8-42c8-b294-5706ce23a47d")
    manager = EventManager("test", "amqp://test-queue-uri", celery_mock, "queue", lambda x: channel_mock)
    event = ScanProfileDBEvent(
        operation_type=OperationType.CREATE,
        valid_time=datetime(2023, 1, 1),
        new_data=empty_scan_profile,
        reference="test|reference",
        client="test",
    )
    manager.publish(event)

    celery_mock.send_task.assert_called_once_with(
        "octopoes.tasks.tasks.handle_event",
        (
            {
                "entity_type": "scan_profile",
                "operation_type": "create",
                "valid_time": "2023-01-01T00:00:00",
                "client": "test",
                "old_data": None,
                "new_data": {"scan_profile_type": "empty", "reference": "test|reference", "level": 0, "user_id": None},
                "reference": "test|reference",
            },
        ),
        queue="queue",
        task_id="1754a4c8-f0b8-42c8-b294-5706ce23a47d",
    )

    call_args = channel_mock.basic_publish.call_args

    actual_body = json.loads(call_args.kwargs["body"])

    expected_body = {
        "operation": "create",
        "primary_key": "test|reference",
        "value": {
            "primary_key": "test|reference",
            "object_type": "test",
            "scan_profile": {"scan_profile_type": "empty", "reference": "test|reference", "level": 0, "user_id": None},
        },
        "client_id": "test",
    }

    assert actual_body == expected_body


def test_event_manager_create_declared_scan_profile(mocker, declared_scan_profile):
    celery_mock = mocker.Mock()
    channel_mock = mocker.Mock()

    mocker.patch.object(uuid, "uuid4", return_value="1754a4c8-f0b8-42c8-b294-5706ce23a47d")
    manager = EventManager("test", "amqp://test-queue-uri", celery_mock, "queue", lambda x: channel_mock)
    event = ScanProfileDBEvent(
        operation_type=OperationType.CREATE,
        valid_time=datetime(2023, 1, 1),
        new_data=declared_scan_profile,
        reference="test|reference",
        client="test",
    )
    manager.publish(event)

    celery_mock.send_task.assert_called_once_with(
        "octopoes.tasks.tasks.handle_event",
        (
            {
                "entity_type": "scan_profile",
                "operation_type": "create",
                "valid_time": "2023-01-01T00:00:00",
                "client": "test",
                "old_data": None,
                "new_data": {
                    "scan_profile_type": "declared",
                    "reference": "test|reference",
                    "level": 2,
                    "user_id": None,
                },
                "reference": "test|reference",
            },
        ),
        queue="queue",
        task_id="1754a4c8-f0b8-42c8-b294-5706ce23a47d",
    )

    assert channel_mock.basic_publish.call_count == 1
    channel_mock.basic_publish.assert_has_calls(
        [
            mock.call(
                exchange="",
                routing_key="scan_profile_mutations",
                body=mock.ANY,
                properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent),
            )
        ]
    )

    actual_body = json.loads(channel_mock.basic_publish.call_args[1]["body"])

    expected_body = {
        "operation": "create",
        "primary_key": "test|reference",
        "value": {
            "primary_key": "test|reference",
            "object_type": "test",
            "scan_profile": {
                "scan_profile_type": "declared",
                "reference": "test|reference",
                "level": 2,
                "user_id": None,
            },
        },
        "client_id": "test",
    }

    assert actual_body == expected_body


def test_event_manager_delete_empty_scan_profile(mocker, empty_scan_profile):
    celery_mock = mocker.Mock()
    channel_mock = mocker.Mock()

    mocker.patch.object(uuid, "uuid4", return_value="1754a4c8-f0b8-42c8-b294-5706ce23a47d")
    manager = EventManager("test", "amqp://test-queue-uri", celery_mock, "queue", lambda x: channel_mock)
    event = ScanProfileDBEvent(
        operation_type=OperationType.DELETE,
        valid_time=datetime(2023, 1, 1),
        old_data=empty_scan_profile,
        reference="test|reference",
        client="test",
    )
    manager.publish(event)

    celery_mock.send_task.assert_called_once_with(
        "octopoes.tasks.tasks.handle_event",
        (
            {
                "entity_type": "scan_profile",
                "operation_type": "delete",
                "valid_time": "2023-01-01T00:00:00",
                "client": "test",
                "old_data": {"scan_profile_type": "empty", "reference": "test|reference", "level": 0, "user_id": None},
                "new_data": None,
                "reference": "test|reference",
            },
        ),
        queue="queue",
        task_id="1754a4c8-f0b8-42c8-b294-5706ce23a47d",
    )

    channel_mock.basic_publish.assert_called_once()

    args, kwargs = channel_mock.basic_publish.call_args

    assert kwargs["exchange"] == ""
    assert kwargs["routing_key"] == "scan_profile_mutations"

    actual_body = json.loads(kwargs["body"])

    assert actual_body == {"operation": "delete", "primary_key": "test|reference", "value": None, "client_id": "test"}

    assert kwargs["properties"] == pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
