import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

from scheduler import config, models, storage
from scheduler.storage import filters, stores

from tests.factories.organisation import OrganisationFactory
from tests.utils import functions


class ScheduleStoreTestCase(unittest.TestCase):
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
                stores.ScheduleStore.name: stores.ScheduleStore(self.dbconn),
            }
        )

        # Organisation
        self.organisation = OrganisationFactory()

    def tearDown(self):
        models.Base.metadata.drop_all(self.dbconn.engine)
        self.dbconn.engine.dispose()

    def test_create_schedule_calculate_deadline_at(self):
        """When a schedule is created, the deadline_at should be calculated."""
        schedule = models.Schedule(
            scheduler_id="test_scheduler_id", organisation=self.organisation.id, schedule="* * * * *", data={}
        )

        self.assertIsNotNone(schedule.deadline_at)

    def test_create_schedule_explicit_deadline_at(self):
        """When a schedule is created, the deadline_at should be set if it is provided."""
        now = datetime.now(timezone.utc)
        schedule = models.Schedule(
            scheduler_id="test_scheduler_id", organisation=self.organisation.id, data={}, deadline_at=now
        )

        self.assertEqual(schedule.deadline_at, now)

    def test_create_schedule_deadline_at_takes_precedence(self):
        """When a schedule is created, the deadline_at should be set if it is provided."""
        now = datetime.now(timezone.utc)
        schedule = models.Schedule(
            scheduler_id="test_scheduler_id",
            schedule="* * * * *",
            organisation=self.organisation.id,
            data={},
            deadline_at=now,
        )

        self.assertEqual(schedule.deadline_at, now)

    def test_create_schedule(self):
        # Arrange
        scheduler_id = "test_scheduler_id"

        task = functions.create_task(scheduler_id=scheduler_id, organisation=self.organisation.id, priority=1)
        schedule = models.Schedule(
            scheduler_id=scheduler_id, organisation=self.organisation.id, hash=task.hash, data=task.model_dump()
        )

        # Act
        schedule_db = self.mock_ctx.datastores.schedule_store.create_schedule(schedule)

        # Assert
        self.assertEqual(schedule, schedule_db)

    def test_get_schedules(self):
        # Arrange
        scheduler_one = "test_scheduler_one"
        for i in range(5):
            task = functions.create_task(scheduler_id=scheduler_one, organisation=self.organisation.id, priority=1)
            schedule = models.Schedule(
                scheduler_id=scheduler_one, organisation=self.organisation.id, hash=task.hash, data=task.model_dump()
            )
            self.mock_ctx.datastores.schedule_store.create_schedule(schedule)

        scheduler_two = "test_scheduler_two"
        for i in range(5):
            task = functions.create_task(scheduler_id=scheduler_two, organisation=self.organisation.id, priority=1)
            schedule = models.Schedule(
                scheduler_id=scheduler_two, organisation=self.organisation.id, hash=task.hash, data=task.model_dump()
            )
            self.mock_ctx.datastores.schedule_store.create_schedule(schedule)

        schedules_scheduler_one, schedules_scheduler_one_count, _ = (
            self.mock_ctx.datastores.schedule_store.get_schedules(
                filters=storage.filters.FilterRequest(
                    filters={"and": [storage.filters.Filter(column="scheduler_id", operator="eq", value=scheduler_one)]}
                )
            )
        )
        schedules_scheduler_two, schedules_scheduler_two_count, _ = (
            self.mock_ctx.datastores.schedule_store.get_schedules(
                filters=storage.filters.FilterRequest(
                    filters={"and": [storage.filters.Filter(column="scheduler_id", operator="eq", value=scheduler_two)]}
                )
            )
        )

        # Assert
        self.assertEqual(5, len(schedules_scheduler_one))
        self.assertEqual(5, schedules_scheduler_one_count)
        self.assertEqual(5, len(schedules_scheduler_two))
        self.assertEqual(5, schedules_scheduler_two_count)

    def test_get_schedule(self):
        # Arrange
        scheduler_id = "test_scheduler_id"
        task = functions.create_task(scheduler_id=scheduler_id, organisation=self.organisation.id, priority=1)
        schedule = models.Schedule(
            scheduler_id=scheduler_id, organisation=self.organisation.id, hash=task.hash, data=task.model_dump()
        )
        schedule_db = self.mock_ctx.datastores.schedule_store.create_schedule(schedule)

        # Act
        schedule_by_id = self.mock_ctx.datastores.schedule_store.get_schedule(schedule_db.id)

        # Assert
        self.assertEqual(schedule_by_id.id, schedule_db.id)

    def test_get_schedule_by_hash(self):
        # Arrange
        scheduler_id = "test_scheduler_id"
        data = functions.create_test_model()
        schedule = models.Schedule(
            scheduler_id=scheduler_id, organisation=self.organisation.id, hash=data.hash, data=data.model_dump()
        )
        schedule_db = self.mock_ctx.datastores.schedule_store.create_schedule(schedule)

        # Act
        schedule_by_hash = self.mock_ctx.datastores.schedule_store.get_schedule_by_hash(schedule_db.hash)

        # Assert
        self.assertEqual(schedule_by_hash.id, schedule_db.id)
        self.assertEqual(schedule_by_hash.data, schedule_db.data)
        self.assertEqual(schedule_by_hash.hash, schedule_db.hash)

    def test_update_schedule(self):
        # Arrange
        scheduler_id = "test_scheduler_id"
        task = functions.create_task(scheduler_id=scheduler_id, organisation=self.organisation.id, priority=1)
        schedule = models.Schedule(
            scheduler_id=scheduler_id, organisation=self.organisation.id, hash=task.hash, data=task.model_dump()
        )
        schedule_db = self.mock_ctx.datastores.schedule_store.create_schedule(schedule)

        # Assert
        self.assertEqual(schedule_db.enabled, True)

        # Act
        schedule_db.enabled = False
        self.mock_ctx.datastores.schedule_store.update_schedule(schedule_db)

        # Assert
        schedule_db_updated = self.mock_ctx.datastores.schedule_store.get_schedule(schedule_db.id)
        self.assertEqual(schedule_db_updated.enabled, False)

    def test_delete_schedule(self):
        # Arrange
        scheduler_id = "test_scheduler_id"
        task = functions.create_task(scheduler_id=scheduler_id, organisation=self.organisation.id, priority=1)
        schedule = models.Schedule(
            scheduler_id=scheduler_id, organisation=self.organisation.id, hash=task.hash, data=task.model_dump()
        )
        schedule_db = self.mock_ctx.datastores.schedule_store.create_schedule(schedule)

        # Act
        self.mock_ctx.datastores.schedule_store.delete_schedule(schedule_db.id)

        # Assert
        is_schedule_deleted = self.mock_ctx.datastores.schedule_store.get_schedule(schedule_db.id)
        self.assertEqual(is_schedule_deleted, None)

    def test_delete_schedule_ondelete(self):
        """When a schedule is deleted, its tasks should NOT be deleted.
        The schedule_id on the tasks should be set to NULL.
        """
        # Arrange
        scheduler_id = "test_scheduler_id"
        task = functions.create_task(scheduler_id=scheduler_id, organisation=self.organisation.id, priority=1)
        schedule = models.Schedule(
            scheduler_id=scheduler_id, organisation=self.organisation.id, hash=task.hash, data=task.model_dump()
        )
        schedule_db = self.mock_ctx.datastores.schedule_store.create_schedule(schedule)

        task.schedule_id = schedule_db.id
        task_db = self.mock_ctx.datastores.task_store.create_task(task)

        # Assert
        self.assertIsNotNone(self.mock_ctx.datastores.task_store.get_task(task_db.id).schedule_id)

        # Act
        self.mock_ctx.datastores.schedule_store.delete_schedule(schedule_db.id)

        # Assert
        is_schedule_deleted = self.mock_ctx.datastores.schedule_store.get_schedule(schedule_db.id)
        self.assertEqual(is_schedule_deleted, None)
        self.assertIsNone(self.mock_ctx.datastores.task_store.get_task(task_db.id).schedule_id)

        is_task_deleted = self.mock_ctx.datastores.task_store.get_task(task_db.id)
        self.assertIsNotNone(is_task_deleted)
        self.assertIsNone(is_task_deleted.schedule_id)

    # NOTE: skipping this test until task relationship is re-enabled, disabled
    # it for now when we use the model relationship
    @unittest.skip("Disabled until task relationship is re-enabled")
    def test_relationship_schedule_tasks(self):
        # Arrange
        scheduler_id = "test_scheduler_id"
        task = functions.create_task(scheduler_id=scheduler_id, organisation=self.organisation.id)
        schedule = models.Schedule(
            scheduler_id=scheduler_id, organisation=self.organisation.id, hash=task.hash, data=task.model_dump()
        )
        schedule_db = self.mock_ctx.datastores.schedule_store.create_schedule(schedule)

        task.schedule_id = schedule_db.id
        task_db = self.mock_ctx.datastores.task_store.create_task(task)

        # Act
        schedule_tasks = self.mock_ctx.datastores.schedule_store.get_schedule(schedule_db.id).tasks

        # Assert
        self.assertEqual(len(schedule_tasks), 1)
        self.assertEqual(schedule_tasks[0].id, task_db.id)

    def test_get_tasks_filter_related(self):
        # Arrange
        scheduler_id = "test_scheduler_id"
        task = functions.create_task(scheduler_id=scheduler_id, organisation=self.organisation.id)
        schedule = models.Schedule(
            scheduler_id=scheduler_id, organisation=self.organisation.id, hash=task.hash, data=task.model_dump()
        )
        schedule_db = self.mock_ctx.datastores.schedule_store.create_schedule(schedule)

        task.schedule_id = schedule_db.id
        created_task = self.mock_ctx.datastores.task_store.create_task(task)

        f_req = filters.FilterRequest(
            filters={"and": [filters.Filter(column="id", operator="eq", value=created_task.id.hex)]}
        )

        tasks, count, _ = self.mock_ctx.datastores.task_store.get_tasks(filters=f_req)
        self.assertEqual(count, 1)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].schedule_id, schedule_db.id)
