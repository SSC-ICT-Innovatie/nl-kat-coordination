import json
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock
from urllib.parse import quote

from fastapi.testclient import TestClient
from scheduler import config, models, server, storage, utils
from scheduler.server import schemas
from scheduler.storage import stores

from tests.factories import OrganisationFactory
from tests.mocks import queue as mock_queue
from tests.mocks import scheduler as mock_scheduler
from tests.utils import functions
from tests.utils.functions import create_task_push_dict


class APITemplateTestCase(unittest.TestCase):
    def setUp(self):
        # Application Context
        self.mock_ctx = mock.patch("scheduler.context.AppContext").start()
        self.mock_ctx.config = config.settings.Settings()

        # Database
        self.dbconn = storage.DBConn(str(self.mock_ctx.config.db_uri))
        self.dbconn.connect()
        models.Base.metadata.drop_all(self.dbconn.engine)
        models.Base.metadata.create_all(self.dbconn.engine)

        self.mock_ctx.datastores = SimpleNamespace(
            **{
                stores.TaskStore.name: stores.TaskStore(self.dbconn),
                stores.PriorityQueueStore.name: stores.PriorityQueueStore(self.dbconn),
                stores.ScheduleStore.name: stores.ScheduleStore(self.dbconn),
            }
        )

        # Organisation
        self.organisation = OrganisationFactory()

        # Queue and Scheduler
        queue = mock_queue.MockPriorityQueue(
            pq_id=self.organisation.id,
            maxsize=10,
            item_type=functions.TestModel,
            allow_priority_updates=True,
            pq_store=self.mock_ctx.datastores.pq_store,
        )

        self.scheduler = mock_scheduler.MockScheduler(
            ctx=self.mock_ctx, scheduler_id=self.organisation.id, queue=queue, create_schedule=True
        )

        # API server and Test Client
        self.server = server.Server(self.mock_ctx, {self.scheduler.scheduler_id: self.scheduler})
        self.client = TestClient(self.server.api)

    def tearDown(self):
        models.Base.metadata.drop_all(self.dbconn.engine)
        self.scheduler.stop()
        self.dbconn.engine.dispose()


class APISchedulerEndpointTestCase(APITemplateTestCase):
    def test_get_schedulers(self):
        response = self.client.get("/schedulers")
        self.assertEqual(response.status_code, 200)

    def test_get_scheduler(self):
        response = self.client.get(f"/schedulers/{self.scheduler.scheduler_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("id"), self.scheduler.scheduler_id)

    def test_get_scheduler_malformed_id(self):
        response = self.client.get("/schedulers/123.123")
        self.assertEqual(response.status_code, 404)

    def test_push_queue(self):
        self.assertEqual(0, self.scheduler.queue.qsize())

        item = create_task_push_dict(1, self.organisation.id)

        response_post = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=item)
        self.assertEqual(201, response_post.status_code)
        self.assertEqual(1, self.scheduler.queue.qsize())
        self.assertIsNotNone(response_post.json().get("id"))

        # Task should be created
        response_get_task = self.client.get(f"/tasks/{response_post.json().get('id')}")
        self.assertEqual(200, response_get_task.status_code)
        self.assertEqual(response_post.json().get("id"), response_get_task.json().get("id"))

        # Schedule should be created, and schedule_id should be in the
        # response of the post request
        response_get_schedule = self.client.get(f"/schedules/{response_post.json().get('schedule_id')}")
        self.assertEqual(200, response_get_schedule.status_code)
        self.assertEqual(response_post.json().get("schedule_id"), response_get_schedule.json().get("id"))

    def test_push_queue_malformed_item(self):
        item = create_task_push_dict(1, self.organisation.id)
        item["extra_field"] = "extra"

        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=item)
        self.assertEqual(response.status_code, 422)
        self.assertIn("Extra inputs are not permitted", response.text)

    def test_push_incorrect_item_type(self):
        response = self.client.post(
            f"/schedulers/{self.scheduler.scheduler_id}/push", json={"organisation": self.organisation.id, "data": {}}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Bad request error occurred: malformed item"})

    def test_push_queue_full(self):
        # Set maxsize of the queue to 1
        self.scheduler.queue.maxsize = 1

        # Add one task to the queue
        first_item = create_task_push_dict(1, self.organisation.id)
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=first_item)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Try to add another task to the queue through the api
        second_item = create_task_push_dict(2, self.organisation.id)
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=second_item)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(1, self.scheduler.queue.qsize())

    def test_push_queue_full_high_priority(self):
        # Set maxsize of the queue to 1
        self.scheduler.queue.maxsize = 1

        # Add one task to the queue
        first_item = create_task_push_dict(1, self.organisation.id)
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=first_item)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Try to add another task to the queue through the api
        second_item = create_task_push_dict(1, self.organisation.id)
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=second_item)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(2, self.scheduler.queue.qsize())

    def test_push_replace_not_allowed(self):
        """When pushing an item that is already in the queue the item
        shouldn't be pushed.
        """
        # Set queue to not allow duplicates
        self.scheduler.queue.allow_replace = False
        self.scheduler.queue.allow_updates = False
        self.scheduler.queue.allow_priority_updates = False

        # Add one task to the queue
        initial_item = create_task_push_dict(1, self.organisation.id)
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=initial_item)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Add the same item again through the api
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=initial_item)

        # The queue should still have one item
        self.assertEqual(response.status_code, 409)
        self.assertEqual(1, self.scheduler.queue.qsize())
        self.assertIn("Conflict error occurred: queue is not allowed to push items", response.text)

    def test_push_replace_allowed(self):
        # Set queue to not allow duplicates
        self.scheduler.queue.allow_replace = True

        # Add one task to the queue
        initial_item = create_task_push_dict(1, self.organisation.id)
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=initial_item)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Add the same item again through the api
        updated_item = schemas.TaskPush(**initial_item)
        response = self.client.post(
            f"/schedulers/{self.scheduler.scheduler_id}/push", json=updated_item.model_dump(exclude_none=True)
        )

        # The queue should have one item
        self.assertEqual(response.status_code, 201)
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Check if the item on the queue is the replaced item
        self.assertEqual(response.json().get("data").get("id"), str(self.scheduler.queue.peek(0).data.get("id")))

    def test_push_updates_not_allowed(self):
        # Set queue to no allow updates
        self.scheduler.queue.allow_replace = False
        self.scheduler.queue.allow_updates = False
        self.scheduler.queue.allow_priority_updates = False

        # Add one task to the queue
        initial_item = create_task_push_dict(1, self.organisation.id)
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=initial_item)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Update the item
        updated_item = schemas.TaskPush(**initial_item)
        updated_item.id = response.json().get("id")
        updated_item.data["name"] = "updated-name"

        # Try to update the item through the api
        response = self.client.post(
            f"/schedulers/{self.scheduler.scheduler_id}/push", data=updated_item.model_dump_json()
        )

        # The queue should still have one item
        self.assertEqual(response.status_code, 409)
        self.assertEqual(1, self.scheduler.queue.qsize())
        self.assertEqual(response.json(), {"detail": "Conflict error occurred: queue is not allowed to push items"})

    def test_push_updates_allowed(self):
        # Set queue to allow updates
        self.scheduler.queue.allow_updates = True

        # Add one task to the queue
        initial_item = create_task_push_dict(1, self.organisation.id)
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=initial_item)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Update the item
        updated_item = schemas.TaskPush(**initial_item)
        updated_item.id = response.json().get("id")
        updated_item.data["name"] = "updated-name"

        # Try to update the item through the api
        response = self.client.post(
            f"/schedulers/{self.scheduler.scheduler_id}/push", data=updated_item.model_dump_json()
        )
        self.assertEqual(response.status_code, 201)

        # The queue should have one item
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Check if the item on the queue is the updated item
        self.assertEqual(response.json().get("data").get("id"), str(self.scheduler.queue.peek(0).data.get("id")))
        self.assertEqual(response.json().get("data").get("name"), "updated-name")

    def test_push_priority_updates_not_allowed(self):
        # Set queue to no allow updates
        self.scheduler.queue.allow_replace = False
        self.scheduler.queue.allow_updates = True
        self.scheduler.queue.allow_priority_updates = False

        # Add one task to the queue
        initial_item = create_task_push_dict(1, self.organisation.id)
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=initial_item)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Update the item
        updated_item = schemas.TaskPush(**initial_item)
        updated_item.priority = 2

        # Try to update the item through the api
        response = self.client.post(
            f"/schedulers/{self.scheduler.scheduler_id}/push", json=updated_item.model_dump(exclude_none=True)
        )

        # The queue should still have one item
        self.assertEqual(response.status_code, 409)
        self.assertEqual(1, self.scheduler.queue.qsize())
        self.assertEqual(response.json(), {"detail": "Conflict error occurred: queue is not allowed to push items"})

    def test_update_priority_higher(self):
        """When updating the priority of the initial item on the priority queue
        to a higher priority, the updated item should be added to the queue,
        the initial item should be marked as removed, and the initial removed
        from the entry_finder.
        """
        # Set queue to allow updates
        self.scheduler.queue.allow_priority_updates = True

        # Add one task to the queue
        initial_item = create_task_push_dict(2, self.organisation.id)
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=initial_item)
        self.assertEqual(response.status_code, 201)

        # Update priority of the item
        updated_item = schemas.TaskPush(**initial_item)
        updated_item.priority = 1

        # Try to update the item through the api
        response = self.client.post(
            f"/schedulers/{self.scheduler.scheduler_id}/push", json=updated_item.model_dump(exclude_none=True)
        )
        self.assertEqual(response.status_code, 201)

        # The queue should have one item
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Check if the item on the queue is the updated item
        self.assertEqual(response.json().get("data").get("id"), str(self.scheduler.queue.peek(0).data.get("id")))

    def test_update_priority_lower(self):
        """When updating the priority of the initial item on the priority queue
        to a lower priority, the updated item should be added to the queue,
        the initial item should be marked as removed, and the initial removed
        from the entry_finder.
        """
        # Set queue to allow updates
        self.scheduler.queue.allow_priority_updates = True

        # Add one task to the queue
        initial_item = create_task_push_dict(1, self.organisation.id)
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=initial_item)
        self.assertEqual(response.status_code, 201)

        # Update priority of the item
        updated_item = schemas.Task(**initial_item)
        updated_item.id = response.json().get("id")
        updated_item.priority = 2

        # Try to update the item through the api
        response = self.client.post(
            f"/schedulers/{self.scheduler.scheduler_id}/push", json=updated_item.model_dump(exclude_none=True)
        )
        self.assertEqual(response.status_code, 201)

        # The queue should have one item
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Check if the item on the queue is the updated item
        self.assertEqual(response.json().get("data").get("id"), str(self.scheduler.queue.peek(0).data.get("id")))

    def test_pop_queue(self):
        # Add one task to the queue
        initial_item = create_task_push_dict(1, self.organisation.id)
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=initial_item)
        initial_item_id = response.json().get("id")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(1, self.scheduler.queue.qsize())

        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/pop")
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.json().get("results")))
        self.assertEqual(initial_item_id, response.json().get("results")[0].get("id"))
        self.assertEqual(0, self.scheduler.queue.qsize())

        # Status of the item should be DISPATCHED
        get_item = self.client.get(f"/tasks/{initial_item_id}")
        self.assertEqual(get_item.json().get("status"), models.TaskStatus.DISPATCHED.name.lower())

    def test_pop_queue_multiple(self):
        # Add one task to the queue
        first_item = create_task_push_dict(1, self.organisation.id)
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=first_item)
        first_item_id = response.json().get("id")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Add second item to the queue
        second_item = create_task_push_dict(2, self.organisation.id)
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=second_item)
        second_item_id = response.json().get("id")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(2, self.scheduler.queue.qsize())

        # Should get two items, and queue should be empty
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/pop?limit=2")
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(response.json().get("results")))
        self.assertEqual(first_item_id, response.json().get("results")[0].get("id"))
        self.assertEqual(second_item_id, response.json().get("results")[1].get("id"))
        self.assertEqual(0, self.scheduler.queue.qsize())

        # Status of the items should be DISPATCHED
        get_first_item = self.client.get(f"/tasks/{first_item_id}")
        get_second_item = self.client.get(f"/tasks/{second_item_id}")
        self.assertEqual(get_first_item.json().get("status"), models.TaskStatus.DISPATCHED.name.lower())
        self.assertEqual(get_second_item.json().get("status"), models.TaskStatus.DISPATCHED.name.lower())

    def test_pop_queue_multiple_pagination(self):
        # Add 10 tasks to the queue
        for i in range(10):
            item = create_task_push_dict(1, self.organisation.id)
            response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=item)
            self.assertEqual(response.status_code, 201)

        # Queue should have 10 items
        self.assertEqual(10, self.scheduler.queue.qsize())

        # Should get 5 items, and queue should have 5 items
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/pop?limit=5")
        self.assertEqual(200, response.status_code)
        self.assertEqual(5, len(response.json().get("results")))
        self.assertEqual(5, self.scheduler.queue.qsize())

        # Status of the items should be DISPATCHED
        for item in response.json().get("results"):
            get_item = self.client.get(f"/tasks/{item.get('id')}")
            self.assertEqual(get_item.json().get("status"), models.TaskStatus.DISPATCHED.name.lower())

        # Should get 5 items, and queue should be empty
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/pop?limit=5")
        self.assertEqual(200, response.status_code)
        self.assertEqual(5, len(response.json().get("results")))
        self.assertEqual(0, self.scheduler.queue.qsize())

        # Status of the items should be DISPATCHED
        for item in response.json().get("results"):
            get_item = self.client.get(f"/tasks/{item.get('id')}")
            self.assertEqual(get_item.json().get("status"), models.TaskStatus.DISPATCHED.name.lower())

    def test_pop_queue_not_found(self):
        mock_id = uuid.uuid4()
        response = self.client.post(f"/schedulers/{mock_id}/pop")
        self.assertEqual(404, response.status_code)

    def test_pop_queue_filters_two_items(self):
        # Add one task to the queue
        first_item = create_task_push_dict(1, self.organisation.id, data=functions.TestModel(id="123", name="test"))
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=first_item)
        first_item_id = response.json().get("id")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Add second item to the queue
        second_item = create_task_push_dict(2, self.organisation.id, data=functions.TestModel(id="456", name="test"))
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=second_item)
        second_item_id = response.json().get("id")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(2, self.scheduler.queue.qsize())

        # Should get two items, and queue should be empty
        response = self.client.post(
            f"/schedulers/{self.scheduler.scheduler_id}/pop?limit=2",
            json={"filters": [{"column": "data", "field": "name", "operator": "eq", "value": "test"}]},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(response.json().get("results")))
        self.assertEqual(first_item_id, response.json().get("results")[0].get("id"))
        self.assertEqual(second_item_id, response.json().get("results")[1].get("id"))
        self.assertEqual(0, self.scheduler.queue.qsize())

        # Status of the items should be DISPATCHED
        get_first_item = self.client.get(f"/tasks/{first_item_id}")
        get_second_item = self.client.get(f"/tasks/{second_item_id}")
        self.assertEqual(get_first_item.json().get("status"), models.TaskStatus.DISPATCHED.name.lower())
        self.assertEqual(get_second_item.json().get("status"), models.TaskStatus.DISPATCHED.name.lower())

    def test_pop_queue_filters_one_item(self):
        # Add one task to the queue
        first_item = create_task_push_dict(1, self.organisation.id, data=functions.TestModel(id="123", name="test"))
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=first_item)
        first_item_id = response.json().get("id")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Add second item to the queue
        second_item = create_task_push_dict(2, self.organisation.id, data=functions.TestModel(id="456", name="test"))
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=second_item)
        second_item_id = response.json().get("id")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(2, self.scheduler.queue.qsize())

        # Should get the first item, and should still be an item on the queue
        response = self.client.post(
            f"/schedulers/{self.scheduler.scheduler_id}/pop",
            json={"filters": [{"column": "data", "field": "id", "operator": "eq", "value": "123"}]},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.json().get("results")))
        self.assertEqual(first_item_id, response.json().get("results")[0].get("id"))
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Should get the second item, and should be no items on the queue
        response = self.client.post(
            f"/schedulers/{self.scheduler.scheduler_id}/pop",
            json={"filters": [{"column": "data", "field": "id", "operator": "eq", "value": "456"}]},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.json().get("results")))
        self.assertEqual(second_item_id, response.json().get("results")[0].get("id"))
        self.assertEqual(0, self.scheduler.queue.qsize())

    def test_pop_queue_filters_nested(self):
        # Add one task to the queue
        first_item = create_task_push_dict(
            1, self.organisation.id, data=functions.TestModel(id="123", name="test", categories=["foo", "bar"])
        )
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=first_item)
        first_item_id = response.json().get("id")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Add second item to the queue
        second_item = create_task_push_dict(
            2, self.organisation.id, data=functions.TestModel(id="456", name="test", categories=["baz", "bat"])
        )
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=second_item)
        second_item_id = response.json().get("id")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(2, self.scheduler.queue.qsize())

        # Should get the first item
        response = self.client.post(
            f"/schedulers/{self.scheduler.scheduler_id}/pop",
            json={
                "filters": [{"column": "data", "operator": "@>", "value": json.dumps({"categories": ["foo", "bar"]})}]
            },
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(first_item_id, response.json().get("results")[0].get("id"))
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Should not return any items
        response = self.client.post(
            f"/schedulers/{self.scheduler.scheduler_id}/pop",
            json={
                "filters": [{"column": "data", "operator": "@>", "value": json.dumps({"categories": ["foo", "bar"]})}]
            },
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, len(response.json().get("results")))
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Should get the second item
        response = self.client.post(
            f"/schedulers/{self.scheduler.scheduler_id}/pop",
            json={
                "filters": [{"column": "data", "operator": "@>", "value": json.dumps({"categories": ["baz", "bat"]})}]
            },
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(second_item_id, response.json().get("results")[0].get("id"))
        self.assertEqual(0, self.scheduler.queue.qsize())

    def test_pop_queue_filters_nested_contained_by(self):
        # Add one task to the queue
        first_item = create_task_push_dict(
            1, self.organisation.id, data=functions.TestModel(id="123", name="test", categories=["foo", "bar"])
        )
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=first_item)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Add second item to the queue
        second_item = create_task_push_dict(
            2, self.organisation.id, data=functions.TestModel(id="456", name="test", categories=["baz", "bat"])
        )
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=second_item)
        second_item_id = response.json().get("id")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(2, self.scheduler.queue.qsize())

        # Test contained by
        response = self.client.post(
            f"/schedulers/{self.scheduler.scheduler_id}/pop",
            json={
                "filters": [
                    {"column": "data", "operator": "<@", "field": "categories", "value": json.dumps(["baz", "bat"])}
                ]
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(second_item_id, response.json().get("results")[0].get("id"))
        self.assertEqual(1, self.scheduler.queue.qsize())

    def test_pop_empty(self):
        """When queue is empty it should return an empty response"""
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/pop")
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, len(response.json().get("results")))


class APITasksEndpointTestCase(APITemplateTestCase):
    def setUp(self):
        super().setUp()

        # Add one task to the queue
        first_item = create_task_push_dict(
            1,
            self.organisation.id,
            data=functions.TestModel(id="123", name="test", child=functions.TestModel(id="123.123", name="test.child")),
        )
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=first_item)
        initial_item_id = response.json().get("id")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(1, self.scheduler.queue.qsize())

        self.first_item_api = self.client.get(f"/tasks/{initial_item_id}").json()

        # Add second item to the queue
        second_item = create_task_push_dict(1, self.organisation.id, data=functions.TestModel(id="456", name="test"))
        response = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=second_item)
        second_item_id = response.json().get("id")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(2, self.scheduler.queue.qsize())

        self.second_item_api = self.client.get(f"/tasks/{second_item_id}").json()

    def test_create_task(self):
        item = create_task_push_dict(1, self.organisation.id)
        response_post = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=item)
        self.assertEqual(201, response_post.status_code)

        initial_item_id = response_post.json().get("id")
        response_get = self.client.get(f"/tasks/{initial_item_id}")
        self.assertEqual(200, response_get.status_code)

        # Task should be created
        response_get_task = self.client.get(f"/tasks/{initial_item_id}")
        self.assertEqual(200, response_get_task.status_code)
        self.assertEqual(initial_item_id, response_get_task.json().get("id"))

        # Schedule should be created
        response_get_schedule = self.client.get(f"/schedules?hash{response_post.json().get('hash')}")
        self.assertEqual(200, response_get_schedule.status_code)
        self.assertEqual(response_post.json().get("hash"), response_get_schedule.json().get("results")[0].get("hash"))

    def test_get_tasks(self):
        response = self.client.get("/tasks")
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, response.json()["count"])
        self.assertEqual(2, len(response.json()["results"]))

    def test_get_task(self):
        # First add a task
        item = create_task_push_dict(1, self.organisation.id)

        response_post = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=item)
        self.assertEqual(201, response_post.status_code)
        initial_item_id = response_post.json().get("id")

        # Then get the task
        response_get = self.client.get(f"/tasks/{initial_item_id}")
        self.assertEqual(200, response_get.status_code, 200)
        self.assertEqual(initial_item_id, response_get.json().get("id"))

    def test_get_task_malformed_id(self):
        response = self.client.get("/tasks/123.123")
        self.assertEqual(422, response.status_code)
        self.assertIn("Input should be a valid UUID", str(response.content))

    def test_get_task_not_found(self):
        mock_id = uuid.uuid4()
        response = self.client.get(f"/tasks/{mock_id}")
        self.assertEqual(404, response.status_code)
        self.assertEqual({"detail": f"Resource not found: task not found, by task_id: {mock_id}"}, response.json())

    def test_get_tasks_min_and_max_created_at(self):
        # Get tasks based on datetime, both min_created_at and max_created_at, should return 2 items
        params = {
            "min_created_at": self.first_item_api.get("created_at"),
            "max_created_at": self.second_item_api.get("created_at"),
        }

        response = self.client.get("/tasks", params=params)
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(response.json()["results"]))

        # Get tasks based on datetime, both min_created_at and max_created_at, should return 1 item
        params = {
            "min_created_at": self.first_item_api.get("created_at"),
            "max_created_at": self.first_item_api.get("created_at"),
        }
        response = self.client.get("/tasks", params=params)
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.json()["results"]))

    def test_get_tasks_min_created_at(self):
        # Get tasks based on datetime, only min_created_at, should return 2 items
        params = {"min_created_at": self.first_item_api.get("created_at")}
        response = self.client.get("/tasks", params=params)
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(response.json()["results"]))

        # Get tasks based on datetime, only min_created_at, should return 1 item
        params = {"min_created_at": self.second_item_api.get("created_at")}
        response = self.client.get("/tasks", params=params)
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.json()["results"]))
        self.assertEqual(self.second_item_api.get("id"), response.json()["results"][0]["id"])

    def test_get_tasks_max_created_at(self):
        # Get tasks based on datetime, only max_created_at, should return 2 items
        params = {"max_created_at": self.second_item_api.get("created_at")}
        response = self.client.get("/tasks", params=params)
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(response.json()["results"]))

        # Get tasks based on datetime, only max_created_at, should return 1 item
        params = {"max_created_at": self.first_item_api.get("created_at")}
        response = self.client.get("/tasks", params=params)
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.json()["results"]))
        self.assertEqual(self.first_item_api.get("id"), response.json()["results"][0]["id"])

    def test_get_tasks_min_greater_than_max_created_at(self):
        # Get tasks min_created_at greater than max_created_at, should return an error
        params = {
            "min_created_at": self.second_item_api.get("created_at"),
            "max_created_at": self.first_item_api.get("created_at"),
        }
        response = self.client.get("/tasks", params=params)
        self.assertEqual(400, response.status_code)
        self.assertEqual(
            {"detail": "Bad request error occurred: min_created_at must be less than max_created_at"}, response.json()
        )

    def test_get_tasks_min_created_at_future(self):
        # Get tasks based on datetime for something in the future, should return 0 items
        params = {"min_created_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}
        response = self.client.get("/tasks", params=params)
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, len(response.json()["results"]))

    def test_get_normalizer_filtered(self):
        # This used to be a bug where the normalizer filter was missing a nesting on the operator
        params = {"task_type": "normalizer", "plugin_id": "kat_nmap_normalize"}
        response = self.client.get("/tasks", params=params)
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, len(response.json()["results"]))

    def test_get_tasks_filtered(self):
        response = self.client.post(
            "/tasks", json={"filters": [{"column": "data", "field": "name", "operator": "eq", "value": "test"}]}
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(response.json()["results"]))

        response = self.client.post(
            "/tasks", json={"filters": [{"column": "data", "field": "id", "operator": "eq", "value": "123"}]}
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.json()["results"]))

        response = self.client.post(
            "/tasks",
            json={"filters": [{"column": "data", "field": "child__name", "operator": "eq", "value": "test.child"}]},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.json()["results"]))

    def test_get_tasks_by_schedule(self):
        # Get tasks based on related schedule attributes
        response = self.client.post(
            "/tasks",
            json={
                "filters": [
                    {
                        "column": "schedule",
                        "field": "deadline_at",
                        "operator": "gt",
                        "value": datetime.now().isoformat(),
                    }
                ]
            },
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(response.json()["results"]))

        response = self.client.post(
            "/tasks",
            json={
                "filters": [
                    {
                        "column": "schedule",
                        "field": "deadline_at",
                        "operator": "lt",
                        "value": datetime.now().isoformat(),
                    }
                ]
            },
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, len(response.json()["results"]))

    def test_patch_task(self):
        # Patch a task
        self.assertEqual(models.TaskStatus.QUEUED.value, self.first_item_api.get("status"))
        response = self.client.patch(f"/tasks/{self.first_item_api.get('id')}", json={"status": "completed"})
        self.assertEqual(200, response.status_code)
        self.assertEqual("completed", response.json().get("status"))

    def test_patch_task_empty(self):
        # Patch a task with empty body
        response = self.client.patch(f"/tasks/{self.first_item_api.get('id')}", json={})
        self.assertEqual(400, response.status_code)
        self.assertEqual({"detail": "Bad request error occurred: no data to patch"}, response.json())

    def test_patch_task_invalid_content(self):
        # Patch a task with invalid content
        response = self.client.patch(f"/tasks/{self.first_item_api.get('id')}", json={"invalid": "invalid"})
        self.assertEqual(400, response.status_code)
        self.assertEqual({"detail": "Bad request error occurred: no data to patch"}, response.json())

    def test_patch_task_not_found(self):
        # Patch a task that does not exist
        mock_id = uuid.uuid4()
        response = self.client.patch(f"/tasks/{mock_id}", json={"status": "completed"})
        self.assertEqual(404, response.status_code)
        self.assertEqual({"detail": f"Resource not found: task not found, by task_id: {mock_id}"}, response.json())

    def test_patch_task_malformed_id(self):
        # Patch a task with malformed id
        response = self.client.patch("/tasks/123.123", json={"status": "completed"})
        self.assertEqual(422, response.status_code)
        self.assertIn("Input should be a valid UUID", response.text)

    def test_patch_task_invalid_status(self):
        # Patch a task with invalid status
        response = self.client.patch(f"/tasks/{self.first_item_api.get('id')}", json={"status": "invalid"})
        self.assertEqual(422, response.status_code)
        self.assertIn("Input should be", response.json().get("detail")[0].get("msg"))

    def test_get_tasks_stats(self):
        response = self.client.get("/tasks/stats")
        self.assertEqual(200, response.status_code)

        response = self.client.get(f"/tasks/stats?scheduler_id={self.first_item_api.get('scheduler_id')}")
        self.assertEqual(200, response.status_code)

        response = self.client.get(f"/tasks/stats?organisation_id={self.first_item_api.get('organisation_id')}")
        self.assertEqual(200, response.status_code)


class APIScheduleEndpointTestCase(APITemplateTestCase):
    def setUp(self):
        super().setUp()

        self.first_item = functions.create_task(self.scheduler.scheduler_id, self.organisation.id)
        self.first_schedule = self.mock_ctx.datastores.schedule_store.create_schedule(
            models.Schedule(
                scheduler_id=self.scheduler.scheduler_id,
                organisation=self.organisation.id,
                hash=self.first_item.hash,
                data=self.first_item.data,
                deadline_at=datetime.now(timezone.utc) + timedelta(days=1),
            )
        )

        self.second_item = functions.create_task(self.scheduler.scheduler_id, self.organisation.id)
        self.second_schedule = self.mock_ctx.datastores.schedule_store.create_schedule(
            models.Schedule(
                scheduler_id=self.scheduler.scheduler_id,
                organisation=self.organisation.id,
                hash=self.second_item.hash,
                data=self.second_item.data,
                deadline_at=datetime.now(timezone.utc) + timedelta(days=2),
            )
        )

    def test_list_schedules(self):
        response = self.client.get("/schedules")
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, response.json()["count"])
        self.assertEqual(2, len(response.json()["results"]))

    def test_list_schedules_scheduler_id(self):
        response = self.client.get(f"/schedules?scheduler_id={self.scheduler.scheduler_id}")
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, response.json()["count"])
        self.assertEqual(2, len(response.json()["results"]))

        response = self.client.get(f"/schedules?scheduler_id={uuid.uuid4()}")
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, response.json()["count"])
        self.assertEqual(0, len(response.json()["results"]))

    def test_list_schedules_enabled(self):
        response = self.client.get("/schedules?enabled=true")
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, response.json()["count"])
        self.assertEqual(2, len(response.json()["results"]))

        response = self.client.get("/schedules?enabled=false")
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, response.json()["count"])
        self.assertEqual(0, len(response.json()["results"]))

    def test_list_schedules_min_deadline(self):
        response = self.client.get(f"/schedules?min_deadline_at={quote(self.first_schedule.deadline_at.isoformat())}")
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, response.json()["count"])
        self.assertEqual(2, len(response.json()["results"]))

        response = self.client.get(f"/schedules?min_deadline_at={quote(self.second_schedule.deadline_at.isoformat())}")
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, response.json()["count"])
        self.assertEqual(1, len(response.json()["results"]))
        self.assertEqual(str(self.second_schedule.id), response.json()["results"][0]["id"])

    def test_list_schedules_max_deadline(self):
        response = self.client.get(f"/schedules?max_deadline_at={quote(self.second_schedule.deadline_at.isoformat())}")
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, response.json()["count"])
        self.assertEqual(2, len(response.json()["results"]))

        response = self.client.get(f"/schedules?max_deadline_at={quote(self.first_schedule.deadline_at.isoformat())}")
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, response.json()["count"])
        self.assertEqual(1, len(response.json()["results"]))
        self.assertEqual(str(self.first_schedule.id), response.json()["results"][0]["id"])

    def test_list_schedules_min_and_max_deadline(self):
        response = self.client.get(
            f"/schedules?min_deadline_at={quote(self.first_schedule.deadline_at.isoformat())}&max_deadline_at={quote(self.second_schedule.deadline_at.isoformat())}"
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(2, response.json()["count"])
        self.assertEqual(2, len(response.json()["results"]))

        response = self.client.get(
            f"/schedules?min_deadline_at={quote(self.first_schedule.deadline_at.isoformat())}&max_deadline_at={quote(self.first_schedule.deadline_at.isoformat())}"
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, response.json()["count"])
        self.assertEqual(1, len(response.json()["results"]))
        self.assertEqual(str(self.first_schedule.id), response.json()["results"][0]["id"])

    def test_list_schedules_min_greater_than_max_deadline(self):
        response = self.client.get(
            f"/schedules?min_deadline_at={quote(self.second_schedule.deadline_at.isoformat())}&max_deadline_at={quote(self.first_schedule.deadline_at.isoformat())}"
        )
        self.assertEqual(400, response.status_code)
        self.assertEqual(
            response.json(), {"detail": "Bad request error occurred: min_deadline_at must be less than max_deadline_at"}
        )

    def test_list_schedules_hash(self):
        response = self.client.get(f"/schedules?schedule_hash={self.first_schedule.hash}")
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, response.json()["count"])
        self.assertEqual(1, len(response.json()["results"]))
        self.assertEqual(str(self.first_schedule.id), response.json()["results"][0]["id"])

    def test_list_schedules_min_created_at(self):
        response = self.client.get(f"/schedules?min_created_at={quote(self.first_schedule.created_at.isoformat())}")
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, response.json()["count"])
        self.assertEqual(2, len(response.json()["results"]))

        response = self.client.get(f"/schedules?min_created_at={quote(self.second_schedule.created_at.isoformat())}")
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, response.json()["count"])
        self.assertEqual(1, len(response.json()["results"]))
        self.assertEqual(str(self.second_schedule.id), response.json()["results"][0]["id"])

    def test_list_schedules_max_created_at(self):
        response = self.client.get(f"/schedules?max_created_at={quote(self.second_schedule.created_at.isoformat())}")
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, response.json()["count"])
        self.assertEqual(2, len(response.json()["results"]))

        response = self.client.get(f"/schedules?max_created_at={quote(self.first_schedule.created_at.isoformat())}")
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, response.json()["count"])
        self.assertEqual(1, len(response.json()["results"]))
        self.assertEqual(str(self.first_schedule.id), response.json()["results"][0]["id"])

    def test_list_schedules_min_and_max_created_at(self):
        response = self.client.get(
            f"/schedules?min_created_at={quote(self.first_schedule.created_at.isoformat())}&max_created_at={quote(self.second_schedule.created_at.isoformat())}"
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, response.json()["count"])
        self.assertEqual(2, len(response.json()["results"]))

        response = self.client.get(
            f"/schedules?min_created_at={quote(self.first_schedule.created_at.isoformat())}&max_created_at={quote(self.first_schedule.created_at.isoformat())}"
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, response.json()["count"])
        self.assertEqual(1, len(response.json()["results"]))
        self.assertEqual(str(self.first_schedule.id), response.json()["results"][0]["id"])

    def test_list_schedules_organisation(self):
        response = self.client.get(f"/schedules?organisation={self.organisation.id}")
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, response.json()["count"])
        self.assertEqual(2, len(response.json()["results"]))

        response = self.client.get(f"/schedules?organisation={uuid.uuid4()}")
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, response.json()["count"])
        self.assertEqual(0, len(response.json()["results"]))

    def test_post_schedule(self):
        item = functions.create_task(self.scheduler.scheduler_id, self.organisation.id)
        response = self.client.post(
            "/schedules",
            json={
                "scheduler_id": item.scheduler_id,
                "organisation": self.organisation.id,
                "schedule": "*/5 * * * *",
                "data": item.data,
            },
        )
        self.assertEqual(201, response.status_code)
        self.assertEqual(item.hash, response.json().get("hash"))
        self.assertEqual(item.data, response.json().get("data"))

        # Deadline should be set to the next run of the schedule
        self.assertEqual(
            utils.cron.next_run("*/5 * * * *"),
            # NOTE: Remove Z from the end of the string. Until 3.11
            # datetime.fromisoformat does not accept Z at the end of the string
            datetime.fromisoformat(response.json().get("deadline_at")[:-1]).astimezone(timezone.utc),
        )

    def test_post_schedule_explicit_deadline_at(self):
        """When a schedule is created, the deadline_at should be set if it is provided."""
        item = functions.create_task(self.scheduler.scheduler_id, self.organisation.id)
        now = datetime.now(timezone.utc)
        response = self.client.post(
            "/schedules",
            json={
                "scheduler_id": item.scheduler_id,
                "organisation": self.organisation.id,
                "data": item.data,
                "deadline_at": now.isoformat(),
            },
        )
        self.assertEqual(201, response.status_code)
        self.assertIsNone(response.json().get("schedule"))
        self.assertEqual(
            # NOTE: Remove Z from the end of the string. Until 3.11
            # datetime.fromisoformat does not accept Z at the end of the string
            datetime.fromisoformat(response.json().get("deadline_at")[:-1]).astimezone(timezone.utc),
            now,
        )

    def test_post_schedule_schedule_and_deadline_at_none(self):
        """When a schedule is created, both schedule and deadline_at should not be None."""
        item = functions.create_task(self.scheduler.scheduler_id, self.organisation.id)
        response = self.client.post(
            "/schedules",
            json={"scheduler_id": item.scheduler_id, "organisation": self.organisation.id, "data": item.data},
        )
        self.assertEqual(400, response.status_code)
        self.assertEqual(
            {"detail": "Bad request error occurred: Either deadline_at or schedule must be provided"}, response.json()
        )

    def test_post_schedule_invalid_schedule(self):
        item = functions.create_task(self.scheduler.scheduler_id, self.organisation.id)
        response = self.client.post(
            "/schedules",
            json={
                "scheduler_id": item.scheduler_id,
                "organisation": self.organisation.id,
                "schedule": "invalid",
                "data": item.data,
            },
        )
        self.assertEqual(400, response.status_code)
        self.assertIn("validation error", response.json().get("detail"))

    def test_post_schedule_invalid_scheduler_id(self):
        item = functions.create_task(self.scheduler.scheduler_id, self.organisation.id)
        response = self.client.post(
            "/schedules",
            json={
                "scheduler_id": "invalid",
                "organisation": self.organisation.id,
                "schedule": "*/5 * * * *",
                "data": item.data,
            },
        )
        self.assertEqual(400, response.status_code)
        self.assertEqual({"detail": "Bad request error occurred: Scheduler invalid not found"}, response.json())

    def test_post_schedule_invalid_data(self):
        item = functions.create_task(self.scheduler.scheduler_id, self.organisation.id)
        response = self.client.post(
            "/schedules",
            json={
                "scheduler_id": item.scheduler_id,
                "organisation": self.organisation.id,
                "schedule": "*/5 * * * *",
                "data": "invalid",
            },
        )
        self.assertEqual(422, response.status_code)

    def test_post_schedule_invalid_data_type(self):
        item = functions.create_task(self.scheduler.scheduler_id, self.organisation.id)
        response = self.client.post(
            "/schedules",
            json={
                "scheduler_id": item.scheduler_id,
                "organisation": self.organisation.id,
                "schedule": "*/5 * * * *",
                "data": {"invalid": "invalid"},
            },
        )
        self.assertEqual(400, response.status_code)
        self.assertIn("validation error", response.json().get("detail"))

    def test_post_schedule_hash_already_exists(self):
        item = functions.create_task(self.scheduler.scheduler_id, self.organisation.id)
        response = self.client.post(
            "/schedules",
            json={
                "scheduler_id": item.scheduler_id,
                "organisation": self.organisation.id,
                "schedule": "*/5 * * * *",
                "data": item.data,
            },
        )
        self.assertEqual(201, response.status_code)

        response = self.client.post(
            "/schedules",
            json={
                "scheduler_id": item.scheduler_id,
                "organisation": self.organisation.id,
                "schedule": "*/5 * * * *",
                "data": item.data,
            },
        )
        self.assertEqual(409, response.status_code)
        self.assertIn("schedule with the same hash already exists", response.json().get("detail"))

    def test_get_schedule(self):
        response = self.client.get(f"/schedules/{self.first_schedule.id}")
        self.assertEqual(200, response.status_code)
        self.assertEqual(str(self.first_schedule.id), response.json().get("id"))

    def test_patch_schedule(self):
        response = self.client.patch(f"/schedules/{self.first_schedule.id}", json={"enabled": False})
        self.assertEqual(200, response.status_code)
        self.assertEqual(False, response.json().get("enabled"))

    def test_patch_schedule_validate_schedule(self):
        response = self.client.patch(f"/schedules/{self.first_schedule.id}", json={"schedule": "*/5 * * * *"})
        self.assertEqual(200, response.status_code)
        self.assertEqual("*/5 * * * *", response.json().get("schedule"))

    def test_patch_schedule_validate_malformed_schedule(self):
        response = self.client.patch(f"/schedules/{self.first_schedule.id}", json={"schedule": "malformed"})
        self.assertEqual(400, response.status_code)
        self.assertIn("validation error", response.json().get("detail"))

    def test_search_schedule(self):
        response = self.client.post(
            "/schedules/search",
            json={
                "filters": [
                    {"column": "data", "field": "name", "operator": "eq", "value": self.first_item.data.get("name")}
                ]
            },
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, response.json()["count"])
        self.assertEqual(1, len(response.json()["results"]))

    def test_search_schedule_with_pagination(self):
        response = self.client.post(
            "/schedules/search?limit=1",
            json={"filters": [{"column": "scheduler_id", "operator": "eq", "value": self.scheduler.scheduler_id}]},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, response.json()["count"])
        self.assertEqual(1, len(response.json()["results"]))

    def test_delete_schedule(self):
        response = self.client.delete(f"/schedules/{self.first_schedule.id}")
        self.assertEqual(204, response.status_code)

        # Schedule should be deleted
        response = self.client.get(f"/schedules/{self.first_schedule.id}")
        self.assertEqual(404, response.status_code)

    def test_delete_schedule_task_schedule_id(self):
        item = create_task_push_dict(1, self.organisation.id)
        response_post = self.client.post(f"/schedulers/{self.scheduler.scheduler_id}/push", json=item)
        self.assertEqual(201, response_post.status_code)
        self.assertEqual(1, self.scheduler.queue.qsize())
        self.assertIsNotNone(response_post.json().get("id"))

        # Task should be created
        response_get_task = self.client.get(f"/tasks/{response_post.json().get('id')}")
        self.assertEqual(200, response_get_task.status_code)
        self.assertEqual(response_post.json().get("id"), response_get_task.json().get("id"))

        # Schedule should be created, and schedule_id should be in the
        # response of the post request
        response_get_schedule = self.client.get(f"/schedules/{response_post.json().get('schedule_id')}")
        self.assertEqual(200, response_get_schedule.status_code)
        self.assertEqual(response_post.json().get("schedule_id"), response_get_schedule.json().get("id"))

        # Delete the schedule
        response_delete = self.client.delete(f"/schedules/{response_post.json().get('schedule_id')}")
        self.assertEqual(204, response_delete.status_code)

        # Schedule should be deleted
        response_get_schedule = self.client.get(f"/schedules/{response_post.json().get('schedule_id')}")
        self.assertEqual(404, response_get_schedule.status_code)

        # schedule_id should be removed from the task
        response_get_task = self.client.get(f"/tasks/{response_post.json().get('id')}")
        self.assertEqual(200, response_get_task.status_code)
        self.assertIsNone(response_get_task.json().get("schedule_id"))
