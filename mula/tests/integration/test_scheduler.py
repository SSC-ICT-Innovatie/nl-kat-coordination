import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock

from scheduler import config, models, storage
from scheduler.schedulers.queue import InvalidItemError, QueueFullError
from scheduler.storage import stores

from tests.factories import OrganisationFactory
from tests.mocks import item as mock_item
from tests.mocks import queue as mock_queue
from tests.mocks import scheduler as mock_scheduler
from tests.utils import functions


class SchedulerTestCase(unittest.TestCase):
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

        identifier = uuid.uuid4().hex

        queue = mock_queue.MockPriorityQueue(
            pq_id=identifier,
            maxsize=self.mock_ctx.config.pq_maxsize,
            item_type=mock_item.MockData,
            allow_priority_updates=True,
            pq_store=self.mock_ctx.datastores.pq_store,
        )

        self.scheduler = mock_scheduler.MockScheduler(
            ctx=self.mock_ctx, scheduler_id=identifier, queue=queue, create_schedule=True
        )

        # Organisation
        self.organisation = OrganisationFactory()

    def tearDown(self):
        self.scheduler.stop()
        models.Base.metadata.drop_all(self.dbconn.engine)
        self.dbconn.engine.dispose()

    def test_push_items_to_queue(self):
        # Arrange
        items = []
        for i in range(10):
            item = functions.create_task(
                scheduler_id=self.scheduler.scheduler_id, organisation=self.organisation.id, priority=i + 1
            )
            items.append(item)

        # Act
        self.scheduler.push_items_to_queue(items)

        # Assert
        self.assertEqual(10, self.scheduler.queue.qsize())

        for i, item in enumerate(items):
            # Task should be on priority queue
            pq_item = self.scheduler.queue.peek(i)
            self.assertEqual(pq_item.id, item.id)

            # Task should be in datastore, and queued
            task_db = self.mock_ctx.datastores.task_store.get_task(str(item.id))
            self.assertEqual(task_db.id, item.id)
            self.assertEqual(task_db.status, models.TaskStatus.QUEUED)

            # Schedule should be in datastore
            schedule_db = self.mock_ctx.datastores.schedule_store.get_schedule(task_db.schedule_id)
            self.assertIsNotNone(schedule_db)
            self.assertEqual(schedule_db.id, task_db.schedule_id)

    def test_push_item_to_queue(self):
        # Arrange
        item = functions.create_task(
            scheduler_id=self.scheduler.scheduler_id, organisation=self.organisation.id, priority=1
        )

        # Act
        self.scheduler.push_item_to_queue(item)

        # Task should be on priority queue
        pq_item = self.scheduler.queue.peek(0)
        self.assertEqual(1, self.scheduler.queue.qsize())
        self.assertEqual(pq_item.id, item.id)

        # Task should be in datastore, and queued
        task_db = self.mock_ctx.datastores.task_store.get_task(str(item.id))
        self.assertEqual(task_db.id, item.id)
        self.assertEqual(task_db.status, models.TaskStatus.QUEUED)

        # Schedule should be in datastore
        schedule_db = self.mock_ctx.datastores.schedule_store.get_schedule(task_db.schedule_id)
        self.assertIsNotNone(schedule_db)
        self.assertEqual(schedule_db.id, task_db.schedule_id)

    def test_push_item_to_queue_create_schedule_false(self):
        # Arrange
        self.scheduler.create_schedule = False

        item = functions.create_task(
            scheduler_id=self.scheduler.scheduler_id, organisation=self.organisation.id, priority=1
        )

        # Act
        self.scheduler.push_item_to_queue(item)

        # Task should be on priority queue
        pq_item = self.scheduler.queue.peek(0)
        self.assertEqual(1, self.scheduler.queue.qsize())
        self.assertEqual(pq_item.id, item.id)

        # Task should be in datastore, and queued
        task_db = self.mock_ctx.datastores.task_store.get_task(str(item.id))
        self.assertEqual(task_db.id, item.id)
        self.assertEqual(task_db.status, models.TaskStatus.QUEUED)
        self.assertIsNone(task_db.schedule_id)

        # Schedule should not be in datastore
        schedule_db = self.mock_ctx.datastores.schedule_store.get_schedule_by_hash(task_db.hash)
        self.assertIsNone(schedule_db)

    def test_push_item_to_queue_full(self):
        # Arrange
        item = functions.create_task(
            scheduler_id=self.scheduler.scheduler_id, organisation=self.organisation.id, priority=1
        )

        self.scheduler.queue.maxsize = 1

        # Act
        self.scheduler.push_item_to_queue_with_timeout(item=item, max_tries=1)

        # Assert
        self.assertEqual(1, self.scheduler.queue.qsize())

        with self.assertRaises(QueueFullError):
            self.scheduler.push_item_to_queue_with_timeout(item=item, max_tries=1)

        self.assertEqual(1, self.scheduler.queue.qsize())

    def test_push_item_to_queue_invalid(self):
        # Arrange
        item = functions.create_task(
            scheduler_id=self.scheduler.scheduler_id, organisation=self.organisation.id, priority=1
        )
        item.data = {"invalid": "data"}

        # Assert
        with self.assertRaises(InvalidItemError):
            self.scheduler.push_item_to_queue(item)

    def test_pop_item_from_queue(self):
        # Arrange
        item = functions.create_task(
            scheduler_id=self.scheduler.scheduler_id, organisation=self.organisation.id, priority=1
        )

        self.scheduler.push_item_to_queue(item)

        # Act
        popped_items = self.scheduler.pop_item_from_queue()

        # Assert
        self.assertEqual(0, self.scheduler.queue.qsize())
        self.assertEqual(1, len(popped_items))
        self.assertEqual(popped_items[0].id, item.id)

        # Status should be dispatched
        task_db = self.mock_ctx.datastores.task_store.get_task(str(item.id))
        self.assertEqual(task_db.status, models.TaskStatus.DISPATCHED)

    def test_post_push(self):
        """When a task is added to the queue, it should be added to the database"""
        # Arrange
        item = functions.create_task(
            scheduler_id=self.scheduler.scheduler_id, organisation=self.organisation.id, priority=1
        )

        # Act
        self.scheduler.push_item_to_queue(item)

        # Assert: Task should be on priority queue
        pq_item = self.scheduler.queue.peek(0)
        self.assertEqual(1, self.scheduler.queue.qsize())
        self.assertEqual(pq_item.id, item.id)

        # Assert: Task should be in datastore, and queued
        task_db = self.mock_ctx.datastores.task_store.get_task(str(item.id))
        self.assertEqual(task_db.id, item.id)
        self.assertEqual(task_db.status, models.TaskStatus.QUEUED)

        # Assert: Schedule should be in datastore
        schedule_db = self.mock_ctx.datastores.schedule_store.get_schedule(task_db.schedule_id)
        self.assertIsNotNone(schedule_db)
        self.assertEqual(schedule_db.id, task_db.schedule_id)

        # Assert: schedule should have a deadline
        self.assertIsNotNone(schedule_db.deadline_at)

        # Assert Schedule cron should NOT be set
        self.assertIsNone(schedule_db.schedule)

        # Assert: deadline should be in the future, at least later than the
        # grace period
        self.assertGreater(schedule_db.deadline_at, datetime.now(timezone.utc))

    def test_post_push_schedule_enabled(self):
        # Arrange
        item = functions.create_task(
            scheduler_id=self.scheduler.scheduler_id, organisation=self.organisation.id, priority=1
        )

        # Act
        self.scheduler.push_item_to_queue(item)

        # Assert: Task should be on priority queue
        pq_item = self.scheduler.queue.peek(0)
        self.assertEqual(1, self.scheduler.queue.qsize())
        self.assertEqual(pq_item.id, item.id)

        # Assert: Task should be in datastore, and queued
        task_db = self.mock_ctx.datastores.task_store.get_task(str(item.id))
        self.assertEqual(task_db.id, item.id)
        self.assertEqual(task_db.status, models.TaskStatus.QUEUED)

        # Assert: Schedule should be in datastore
        schedule_db = self.mock_ctx.datastores.schedule_store.get_schedule(task_db.schedule_id)
        self.assertIsNotNone(schedule_db)
        self.assertEqual(schedule_db.id, task_db.schedule_id)

        # Assert: schedule should have a deadline
        self.assertIsNotNone(schedule_db.deadline_at)

        # Assert Schedule cron should NOT be set
        self.assertIsNone(schedule_db.schedule)

        # Assert: deadline should be in the future, at least later than the
        # grace period
        self.assertGreater(schedule_db.deadline_at, datetime.now(timezone.utc))

    def test_post_push_schedule_update_schedule(self):
        # Arrange
        first_item = functions.create_task(
            scheduler_id=self.scheduler.scheduler_id, organisation=self.organisation.id, priority=1
        )

        # Act
        first_item_db = self.scheduler.push_item_to_queue(first_item)

        initial_schedule_db = self.mock_ctx.datastores.schedule_store.get_schedule(first_item_db.schedule_id)

        # Pop
        self.scheduler.pop_item_from_queue()

        # Act
        second_item = first_item_db.model_copy()
        second_item.id = uuid.uuid4()
        second_item_db = self.scheduler.push_item_to_queue(second_item)

        updated_schedule_db = self.mock_ctx.datastores.schedule_store.get_schedule(second_item_db.schedule_id)

        # Assert
        self.assertEqual(initial_schedule_db.id, updated_schedule_db.id)
        self.assertNotEqual(updated_schedule_db.deadline_at, initial_schedule_db.deadline_at)

        # There should be only one schedule
        schedules, _, _ = self.mock_ctx.datastores.schedule_store.get_schedules(
            scheduler_id=self.scheduler.scheduler_id
        )

        self.assertEqual(1, len(schedules))

    def test_post_push_schedule_is_not_none(self):
        """When a schedule is provided, it should be used to set the deadline"""
        # Arrange
        first_item = functions.create_task(
            scheduler_id=self.scheduler.scheduler_id, organisation=self.organisation.id, priority=1
        )

        schedule = models.Schedule(
            scheduler_id=self.scheduler.scheduler_id,
            organisation=self.organisation.id,
            schedule="0 0 * * *",
            hash=first_item.hash,
            data=first_item.data,
        )
        schedule_db = self.mock_ctx.datastores.schedule_store.create_schedule(schedule)

        first_item.schedule_id = schedule_db.id
        self.mock_ctx.datastores.task_store.update_task(first_item)

        # Act
        self.scheduler.push_item_to_queue(first_item)

        # Assert: Check if the deadline_at is set correctly, to the next
        # day at midnight
        self.assertEqual(
            schedule_db.deadline_at,
            datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
        )

    def test_post_push_schedule_is_none(self):
        """When a schedule is not provided, the deadline should be set to None"""
        # Arrange
        first_item = functions.create_task(
            scheduler_id=self.scheduler.scheduler_id, organisation=self.organisation.id, priority=1
        )

        schedule = models.Schedule(
            scheduler_id=self.scheduler.scheduler_id,
            organisation=self.organisation.id,
            hash=first_item.hash,
            data=first_item.data,
        )
        schedule_db = self.mock_ctx.datastores.schedule_store.create_schedule(schedule)

        first_item.schedule_id = schedule_db.id
        self.mock_ctx.datastores.task_store.update_task(first_item)

        # Act
        self.scheduler.push_item_to_queue(first_item)

        # Assert:
        self.assertIsNone(schedule_db.deadline_at)

    def test_post_push_schedule_auto_calculate_deadline(self):
        """When a schedule is not provided, and auto_calculate_deadline is True, the deadline should be set"""
        # Arrange
        self.scheduler.auto_calculate_deadline = True

        first_item = functions.create_task(
            scheduler_id=self.scheduler.scheduler_id, organisation=self.organisation.id, priority=1
        )

        schedule = models.Schedule(
            scheduler_id=self.scheduler.scheduler_id,
            organisation=self.organisation.id,
            hash=first_item.hash,
            data=first_item.data,
        )
        schedule_db = self.mock_ctx.datastores.schedule_store.create_schedule(schedule)

        first_item.schedule_id = schedule_db.id
        self.mock_ctx.datastores.task_store.update_task(first_item)

        # Act
        self.scheduler.push_item_to_queue(first_item)

        # Assert: Check if the deadline_at is set correctly
        schedule_db_updated = self.mock_ctx.datastores.schedule_store.get_schedule(first_item.schedule_id)
        self.assertIsNotNone(schedule_db_updated.deadline_at)

    def test_post_pop(self):
        """When a task is popped from the queue, it should be removed from the database"""
        # Arrange
        item = functions.create_task(
            scheduler_id=self.scheduler.scheduler_id, organisation=self.organisation.id, priority=1
        )

        # Act
        self.scheduler.push_item_to_queue(item)

        # Assert: task should be on priority queue
        pq_item = self.scheduler.queue.peek(0)
        self.assertEqual(1, self.scheduler.queue.qsize())
        self.assertEqual(pq_item.id, item.id)

        # Assert: task should be in datastore, and queued
        task_db = self.mock_ctx.datastores.task_store.get_task(str(item.id))
        self.assertEqual(task_db.id, item.id)
        self.assertEqual(task_db.status, models.TaskStatus.QUEUED)

        # Act
        self.scheduler.pop_item_from_queue()

        # Assert: task should be in datastore, and dispatched
        self.assertEqual(0, self.scheduler.queue.qsize())
        task_db = self.mock_ctx.datastores.task_store.get_task(str(item.id))
        self.assertEqual(task_db.id, item.id)
        self.assertEqual(task_db.status, models.TaskStatus.DISPATCHED)
