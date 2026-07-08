import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock

from scheduler import config, models, storage
from scheduler.storage import stores

from tests.factories import OrganisationFactory
from tests.utils import functions


class StoreTestCase(unittest.TestCase):
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
                stores.PriorityQueueStore.name: stores.PriorityQueueStore(self.dbconn),
                stores.TaskStore.name: stores.TaskStore(self.dbconn),
            }
        )

        # Organisation
        self.organisation = OrganisationFactory()

    def tearDown(self):
        models.Base.metadata.drop_all(self.dbconn.engine)
        self.dbconn.engine.dispose()

    def test_create_task(self):
        task = functions.create_task(scheduler_id=self.organisation.id, organisation=self.organisation.id)
        created_task = self.mock_ctx.datastores.task_store.create_task(task)
        self.assertIsNotNone(created_task)

    def test_get_tasks(self):
        # Arrange
        for i in range(5):
            task = functions.create_task(scheduler_id=self.organisation.id, organisation=self.organisation.id)
            self.mock_ctx.datastores.task_store.create_task(task)

        # Act
        tasks, count, _ = self.mock_ctx.datastores.task_store.get_tasks(scheduler_id=self.organisation.id)

        # Assert
        self.assertEqual(len(tasks), 5)
        self.assertEqual(count, 5)

    def get_tasks_by_type(self):
        # Arrange
        for i in range(5):
            task = functions.create_task(scheduler_id=self.organisation.id, organisation=self.organisation.id)
            self.mock_ctx.datastores.task_store.create_task(task)

        # Act
        tasks, count, _ = self.mock_ctx.datastores.task_store.get_tasks(
            scheduler_id=self.organisation.id, task_type=functions.TestModel.type
        )

        # Assert
        self.assertEqual(len(tasks), 5)
        self.assertEqual(count, 5)

    def test_get_tasks_by_hash(self):
        # Arrange
        hashes = []
        data = functions.create_test_model()
        for i in range(5):
            task = functions.create_task(
                scheduler_id=self.organisation.id, organisation=self.organisation.id, data=data
            )
            self.mock_ctx.datastores.task_store.create_task(task)
            hashes.append(task.hash)

        # Every task should have the same hash
        self.assertEqual(len(set(hashes)), 1)

        # Act
        tasks = self.mock_ctx.datastores.task_store.get_tasks_by_hash(data.hash)

        # Assert
        self.assertEqual(len(tasks), 5)

    def test_get_task(self):
        # Arrange
        task = functions.create_task(scheduler_id=self.organisation.id, organisation=self.organisation.id)
        created_task = self.mock_ctx.datastores.task_store.create_task(task)

        # Act
        task = self.mock_ctx.datastores.task_store.get_task(created_task.id)

        # Assert
        self.assertIsNotNone(task)

    def test_get_latest_task_by_hash(self):
        # Arrange
        hashes = []
        data = functions.create_test_model()
        for i in range(5):
            task = functions.create_task(
                scheduler_id=self.organisation.id, organisation=self.organisation.id, data=data
            )
            self.mock_ctx.datastores.task_store.create_task(task)
            hashes.append(task.hash)

        # Every task should have the same hash
        self.assertEqual(len(set(hashes)), 1)

        # Act
        task = self.mock_ctx.datastores.task_store.get_latest_task_by_hash(data.hash)

        # Assert
        self.assertIsNotNone(task)

    def test_update_task(self):
        # Arrange
        task = functions.create_task(scheduler_id=self.organisation.id, organisation=self.organisation.id)
        created_task = self.mock_ctx.datastores.task_store.create_task(task)

        # Act
        created_task.status = models.TaskStatus.COMPLETED
        self.mock_ctx.datastores.task_store.update_task(created_task)

        # Assert
        updated_task = self.mock_ctx.datastores.task_store.get_task(created_task.id)
        self.assertEqual(updated_task.status, models.TaskStatus.COMPLETED)

    def test_cancel_task(self):
        # Arrange
        task = functions.create_task(scheduler_id=self.organisation.id, organisation=self.organisation.id)
        created_task = self.mock_ctx.datastores.task_store.create_task(task)

        # Act
        self.mock_ctx.datastores.task_store.cancel_tasks(self.organisation.id, [created_task.id])

        # Assert
        updated_task = self.mock_ctx.datastores.task_store.get_task(created_task.id)
        self.assertEqual(updated_task.status, models.TaskStatus.CANCELLED)

    def test_get_status_counts(self):
        # Arrange
        one_hour = datetime.now(timezone.utc) - timedelta(hours=1)
        four_hours = datetime.now(timezone.utc) - timedelta(hours=4)
        twenty_three_hours = datetime.now(timezone.utc) - timedelta(hours=23)
        twenty_five_hours = datetime.now(timezone.utc) - timedelta(hours=25)

        for r, status, modified_at in zip(
            (range(2), range(2), range(2), range(2), range(2)),
            (
                models.TaskStatus.QUEUED,
                models.TaskStatus.COMPLETED,
                models.TaskStatus.FAILED,
                models.TaskStatus.DISPATCHED,
                models.TaskStatus.DISPATCHED,
            ),
            (one_hour, four_hours, one_hour, twenty_five_hours, twenty_three_hours),
        ):
            for _ in r:
                data = functions.create_test_model()
                task = models.Task(
                    scheduler_id=self.organisation.id,
                    organisation=self.organisation.id,
                    priority=1,
                    status=status,
                    type=functions.TestModel.type,
                    hash=data.hash,
                    data=data.model_dump(),
                    modified_at=modified_at,
                )
                self.mock_ctx.datastores.task_store.create_task(task)

        # Act
        results = self.mock_ctx.datastores.task_store.get_status_counts()

        # Assert
        self.assertEqual(results[models.TaskStatus.QUEUED.value], 2)
        self.assertEqual(results[models.TaskStatus.COMPLETED.value], 2)
        self.assertEqual(results[models.TaskStatus.FAILED.value], 2)
        self.assertEqual(results[models.TaskStatus.DISPATCHED.value], 4)

    def test_get_status_count_per_hour(self):
        # Arrange
        one_hour = datetime.now(timezone.utc) - timedelta(hours=1)
        four_hours = datetime.now(timezone.utc) - timedelta(hours=4)
        twenty_three_hours = datetime.now(timezone.utc) - timedelta(hours=23)
        twenty_five_hours = datetime.now(timezone.utc) - timedelta(hours=25)

        for r, status, modified_at in zip(
            (range(2), range(2), range(2), range(2), range(2)),
            (
                models.TaskStatus.QUEUED,
                models.TaskStatus.COMPLETED,
                models.TaskStatus.FAILED,
                models.TaskStatus.DISPATCHED,
                models.TaskStatus.DISPATCHED,
            ),
            (one_hour, four_hours, one_hour, twenty_five_hours, twenty_three_hours),
        ):
            for _ in r:
                data = functions.create_test_model()
                task = models.Task(
                    scheduler_id=self.organisation.id,
                    organisation=self.organisation.id,
                    priority=1,
                    status=status,
                    type=functions.TestModel.type,
                    hash=data.hash,
                    data=data.model_dump(),
                    modified_at=modified_at,
                )
                self.mock_ctx.datastores.task_store.create_task(task)

        # Act
        results = self.mock_ctx.datastores.task_store.get_status_count_per_hour()
        keys = [k for k in results]

        # Assert
        self.assertEqual(len(results), 3)
        self.assertEqual(results.get(keys[0]).get("queued"), 2)
        self.assertEqual(results.get(keys[0]).get("failed"), 2)
        self.assertEqual(results.get(keys[0]).get("total"), 4)
        self.assertEqual(results.get(keys[1]).get("completed"), 2)
        self.assertEqual(results.get(keys[1]).get("total"), 2)
        self.assertEqual(results.get(keys[2]).get("dispatched"), 2)
        self.assertEqual(results.get(keys[2]).get("total"), 2)

    def test_get_tasks_bounded_count_below_cap(self):
        # Arrange
        for _ in range(3):
            task = functions.create_task(scheduler_id=self.organisation.id, organisation=self.organisation.id)
            self.mock_ctx.datastores.task_store.create_task(task)

        # Act: max_count = offset(0) + max_pages(6) * limit(2) + 1 = 13, real count 3 < 13
        tasks, count, is_partial_count = self.mock_ctx.datastores.task_store.get_tasks(
            scheduler_id=self.organisation.id, limit=2, max_pages=6, allow_partial_count=True
        )

        # Assert: below the cap the count is exact and not flagged partial
        self.assertEqual(count, 3)
        self.assertFalse(is_partial_count)
        self.assertEqual(len(tasks), 2)

    def test_get_tasks_bounded_count_at_cap(self):
        # Arrange
        for _ in range(10):
            task = functions.create_task(scheduler_id=self.organisation.id, organisation=self.organisation.id)
            self.mock_ctx.datastores.task_store.create_task(task)

        # Act: max_count = offset(0) + max_pages(2) * limit(2) + 1 = 5, real count 10 >= 5
        tasks, count, is_partial_count = self.mock_ctx.datastores.task_store.get_tasks(
            scheduler_id=self.organisation.id, limit=2, max_pages=2, allow_partial_count=True
        )

        # Assert: at/above the cap the count is the bounded max_count and flagged partial
        self.assertEqual(count, 5)
        self.assertTrue(is_partial_count)
        self.assertEqual(len(tasks), 2)

    def test_get_tasks_bounded_count_without_filter(self):
        # Arrange
        for _ in range(3):
            task = functions.create_task(scheduler_id=self.organisation.id, organisation=self.organisation.id)
            self.mock_ctx.datastores.task_store.create_task(task)

        # Act: no filters means the query has no WHERE clause; the bounded count must still
        # project a real column so the FROM clause survives (a bare SELECT 1 collapses to count 1)
        tasks, count, is_partial_count = self.mock_ctx.datastores.task_store.get_tasks(
            limit=150, allow_partial_count=True
        )

        # Assert
        self.assertEqual(count, 3)
        self.assertFalse(is_partial_count)

    def test_get_tasks_limit_zero_returns_full_count(self):
        # Arrange
        for _ in range(4):
            task = functions.create_task(scheduler_id=self.organisation.id, organisation=self.organisation.id)
            self.mock_ctx.datastores.task_store.create_task(task)

        # Act: limit=0 is the count-probe idiom; page size is unknown so no bounded query is possible
        tasks, count, is_partial_count = self.mock_ctx.datastores.task_store.get_tasks(
            scheduler_id=self.organisation.id, limit=0, max_pages=1, allow_partial_count=True
        )

        # Assert: exact count, no results, never partial
        self.assertEqual(count, 4)
        self.assertFalse(is_partial_count)
        self.assertEqual(len(tasks), 0)

    def test_get_tasks_allow_partial_count_false_is_exact(self):
        # Arrange
        for _ in range(10):
            task = functions.create_task(scheduler_id=self.organisation.id, organisation=self.organisation.id)
            self.mock_ctx.datastores.task_store.create_task(task)

        # Act: without allow_partial_count the count is always exact, even past the cap
        tasks, count, is_partial_count = self.mock_ctx.datastores.task_store.get_tasks(
            scheduler_id=self.organisation.id, limit=2, max_pages=2, allow_partial_count=False
        )

        # Assert
        self.assertEqual(count, 10)
        self.assertFalse(is_partial_count)

    def test_get_status_counts_filtered_by_organisation_ids(self):
        # Arrange: two tasks for our organisation, one for another
        other = OrganisationFactory()
        for org in (self.organisation.id, self.organisation.id, other.id):
            data = functions.create_test_model()
            task = models.Task(
                scheduler_id=self.organisation.id,
                organisation=org,
                priority=1,
                status=models.TaskStatus.COMPLETED,
                type=functions.TestModel.type,
                hash=data.hash,
                data=data.model_dump(),
            )
            self.mock_ctx.datastores.task_store.create_task(task)

        # Act
        only_first = self.mock_ctx.datastores.task_store.get_status_counts(organisation_ids=[self.organisation.id])
        both = self.mock_ctx.datastores.task_store.get_status_counts(organisation_ids=[self.organisation.id, other.id])

        # Assert: the IN filter scopes the counts to the requested organisations
        self.assertEqual(only_first[models.TaskStatus.COMPLETED.value], 2)
        self.assertEqual(both[models.TaskStatus.COMPLETED.value], 3)
