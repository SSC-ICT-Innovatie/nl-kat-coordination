import unittest
from types import SimpleNamespace
from unittest import mock

from scheduler import config, models, schedulers, storage
from scheduler.storage import stores

from tests.factories import OrganisationFactory


class ReportSchedulerBaseTestCase(unittest.TestCase):
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

        # Scheduler
        self.scheduler = schedulers.ReportScheduler(ctx=self.mock_ctx)

        # Organisation
        self.organisation = OrganisationFactory()

    def tearDown(self):
        self.scheduler.stop()
        models.Base.metadata.drop_all(self.dbconn.engine)
        self.dbconn.engine.dispose()


class ReportSchedulerTestCase(ReportSchedulerBaseTestCase):
    def setUp(self):
        super().setUp()

        self.mock_get_schedules = mock.patch(
            "scheduler.context.AppContext.datastores.schedule_store.get_schedules"
        ).start()

    def tearDown(self):
        mock.patch.stopall()

    def test_process_rescheduling(self):
        """When the deadline of schedules have passed, the resulting task should be added to the queue"""
        # Arrange
        report_task = models.ReportTask(organisation_id=self.organisation.id, report_recipe_id="123")

        schedule = models.Schedule(
            scheduler_id=self.scheduler.scheduler_id,
            hash=report_task.hash,
            data=report_task.model_dump(),
            organisation=self.organisation.id,
        )

        schedule_db = self.mock_ctx.datastores.schedule_store.create_schedule(schedule)

        # Mocks
        self.mock_get_schedules.return_value = ([schedule_db], 1, False)

        # Act
        self.scheduler.process_rescheduling()

        # Assert: new item should be on queue
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Assert: new item is created with a similar task
        peek = self.scheduler.queue.peek(0)
        self.assertEqual(schedule.hash, peek.hash)

        # Assert: task should be created, and should be the one that is queued
        task_db = self.mock_ctx.datastores.task_store.get_task(peek.id)
        self.assertIsNotNone(task_db)
        self.assertEqual(peek.id, task_db.id)

    def test_process_rescheduling_item_on_queue(self):
        """When the deadline of schedules have passed, the resulting task should be added to the queue"""
        # Arrange
        report_task = models.ReportTask(organisation_id=self.organisation.id, report_recipe_id="123")

        schedule = models.Schedule(
            scheduler_id=self.scheduler.scheduler_id,
            hash=report_task.hash,
            data=report_task.model_dump(),
            organisation=self.organisation.id,
        )

        schedule_db = self.mock_ctx.datastores.schedule_store.create_schedule(schedule)

        # Mocks
        self.mock_get_schedules.return_value = ([schedule_db], 1, False)

        # Act
        self.scheduler.process_rescheduling()

        # Assert: new item should be on queue
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Assert: new item is created with a similar task
        peek = self.scheduler.queue.peek(0)
        self.assertEqual(schedule.hash, peek.hash)

        # Assert: task should be created, and should be the one that is queued
        task_db = self.mock_ctx.datastores.task_store.get_task(peek.id)
        self.assertIsNotNone(task_db)
        self.assertEqual(peek.id, task_db.id)

        # Act: push again
        self.scheduler.process_rescheduling()

        # Should only be one task on queue
        self.assertEqual(1, self.scheduler.queue.qsize())
