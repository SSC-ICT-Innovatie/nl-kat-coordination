import datetime
import unittest
from types import SimpleNamespace
from unittest import mock

from scheduler import config, models, schedulers, storage
from scheduler.storage import stores
from structlog.testing import capture_logs

from tests.factories import (
    BoefjeFactory,
    BoefjeMetaFactory,
    NormalizerFactory,
    OOIFactory,
    OrganisationFactory,
    PluginFactory,
    RawDataFactory,
    ScanProfileFactory,
)
from tests.utils import functions


class NormalizerSchedulerBaseTestCase(unittest.TestCase):
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
        self.scheduler = schedulers.NormalizerScheduler(self.mock_ctx)

        # Organisation
        self.organisation = OrganisationFactory()

    def tearDown(self):
        self.scheduler.stop()
        models.Base.metadata.drop_all(self.dbconn.engine)
        self.dbconn.engine.dispose()


class NormalizerSchedulerTestCase(NormalizerSchedulerBaseTestCase):
    def setUp(self):
        super().setUp()

        self.mock_latest_task_by_hash = mock.patch(
            "scheduler.context.AppContext.datastores.task_store.get_latest_task_by_hash"
        ).start()

        self.mock_get_plugin = mock.patch(
            "scheduler.context.AppContext.services.katalogus.get_plugin_by_id_and_org_id"
        ).start()

    def test_is_allowed_to_run(self):
        # Arrange
        plugin = PluginFactory(type="normalizer", consumes=["text/plain"])

        # Mocks
        self.mock_get_plugin.return_value = plugin

        # Act
        allowed_to_run = self.scheduler.has_normalizer_permission_to_run(plugin)

        # Assert
        self.assertTrue(allowed_to_run)

    def test_is_not_allowed_to_run(self):
        # Arrange
        plugin = PluginFactory(type="normalizer", consumes=["text/plain"])
        plugin.enabled = False

        # Mocks
        self.mock_get_plugin.return_value = plugin

        # Act
        allowed_to_run = self.scheduler.has_normalizer_permission_to_run(plugin)

        # Assert
        self.assertFalse(allowed_to_run)


class RawFileReceivedTestCase(NormalizerSchedulerBaseTestCase):
    def setUp(self):
        super().setUp()

        self.mock_has_normalizer_task_started_running = mock.patch(
            "scheduler.schedulers.NormalizerScheduler.has_normalizer_task_started_running", return_value=False
        ).start()

        self.mock_has_normalizer_permission_to_run = mock.patch(
            "scheduler.schedulers.NormalizerScheduler.has_normalizer_permission_to_run", return_value=True
        ).start()

        self.mock_get_normalizers_for_mime_type = mock.patch(
            "scheduler.context.AppContext.services.katalogus.get_normalizers_by_org_id_and_type"
        ).start()

        self.mock_get_plugin = mock.patch(
            "scheduler.context.AppContext.services.katalogus.get_plugin_by_id_and_org_id"
        ).start()

    def test_process_raw_data(self):
        # Arrange
        ooi = OOIFactory(scan_profile=ScanProfileFactory(level=0))
        boefje = BoefjeFactory()
        boefje_meta = BoefjeMetaFactory(boefje=boefje, input_ooi=ooi.primary_key)

        # Arrange: create the RawDataReceivedEvent
        raw_data_event = models.RawDataReceivedEvent(
            raw_data=RawDataFactory(boefje_meta=boefje_meta, mime_types=[{"value": "text/plain"}]),
            organization=self.organisation.id,
            created_at=datetime.datetime.now(),
        ).model_dump_json()

        # Mocks
        plugin = PluginFactory(type="normalizer", consumes=["text/plain"])
        self.mock_get_normalizers_for_mime_type.return_value = [plugin]

        # Act
        self.scheduler.process_raw_data(raw_data_event)

        # Task should be on priority queue
        task_pq = self.scheduler.queue.peek(0)
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Task should be in datastore
        task_db = self.mock_ctx.datastores.task_store.get_task(task_pq.id)
        self.assertEqual(task_db.id, task_pq.id)
        self.assertEqual(task_db.status, models.TaskStatus.QUEUED)

    def test_process_raw_data_no_normalizers_found(self):
        # Arrange
        ooi = OOIFactory(scan_profile=ScanProfileFactory(level=0))
        boefje = BoefjeFactory()
        boefje_meta = BoefjeMetaFactory(boefje=boefje, input_ooi=ooi.primary_key)

        raw_data_event = models.RawDataReceivedEvent(
            raw_data=RawDataFactory(boefje_meta=boefje_meta, mime_types=[{"value": "text/plain"}]),
            organization=self.organisation.id,
            created_at=datetime.datetime.now(),
        ).model_dump_json()

        # Mocks
        self.mock_get_normalizers_for_mime_type.return_value = []

        # Act
        self.scheduler.process_raw_data(raw_data_event)

        # Task should not be on priority queue
        self.assertEqual(0, self.scheduler.queue.qsize())

    def test_process_raw_data_not_allowed_to_run(self):
        # Arrange
        scan_profile = ScanProfileFactory(level=0)
        ooi = OOIFactory(scan_profile=scan_profile)
        boefje = BoefjeFactory()
        boefje_task = models.BoefjeTask(boefje=boefje, input_ooi=ooi.primary_key, organization=self.organisation.id)

        task = functions.create_task(
            scheduler_id=self.scheduler.scheduler_id, data=boefje_task, organisation=self.organisation.id
        )
        self.mock_ctx.datastores.task_store.create_task(task)

        boefje_meta = BoefjeMetaFactory(boefje=boefje, input_ooi=ooi.primary_key)

        # Mocks
        raw_data_event = models.RawDataReceivedEvent(
            raw_data=RawDataFactory(boefje_meta=boefje_meta, mime_types=[{"value": "text/plain"}]),
            organization=self.organisation.id,
            created_at=datetime.datetime.now(),
        ).model_dump_json()

        self.mock_get_normalizers_for_mime_type.return_value = [NormalizerFactory()]
        self.mock_has_normalizer_permission_to_run.return_value = False

        # Act
        self.scheduler.process_raw_data(raw_data_event)

        # Task should not be on priority queue
        self.assertEqual(0, self.scheduler.queue.qsize())

    def test_process_raw_data_still_running(self):
        # Arrange
        scan_profile = ScanProfileFactory(level=0)
        ooi = OOIFactory(scan_profile=scan_profile)
        boefje = BoefjeFactory()
        boefje_task = models.BoefjeTask(boefje=boefje, input_ooi=ooi.primary_key, organization=self.organisation.id)

        task = functions.create_task(
            scheduler_id=self.scheduler.scheduler_id, data=boefje_task, organisation=self.organisation.id
        )
        self.mock_ctx.datastores.task_store.create_task(task)

        boefje_meta = BoefjeMetaFactory(boefje=boefje, input_ooi=ooi.primary_key)

        # Mocks
        raw_data_event = models.RawDataReceivedEvent(
            raw_data=RawDataFactory(boefje_meta=boefje_meta, mime_types=[{"value": "text/plain"}]),
            organization=self.organisation.id,
            created_at=datetime.datetime.now(),
        ).model_dump_json()

        self.mock_get_normalizers_for_mime_type.return_value = [NormalizerFactory()]
        self.mock_has_normalizer_permission_to_run.return_value = True
        self.mock_has_normalizer_task_started_running.return_value = True

        # Act
        self.scheduler.process_raw_data(raw_data_event)

        # Task should not be on priority queue
        self.assertEqual(0, self.scheduler.queue.qsize())

    def test_process_raw_data_still_running_exception(self):
        # Arrange
        scan_profile = ScanProfileFactory(level=0)
        ooi = OOIFactory(scan_profile=scan_profile)
        boefje = BoefjeFactory()
        boefje_task = models.BoefjeTask(boefje=boefje, input_ooi=ooi.primary_key, organization=self.organisation.id)

        task = functions.create_task(
            scheduler_id=self.scheduler.scheduler_id, data=boefje_task, organisation=self.organisation.id
        )
        self.mock_ctx.datastores.task_store.create_task(task)

        boefje_meta = BoefjeMetaFactory(boefje=boefje, input_ooi=ooi.primary_key)

        # Mocks
        raw_data_event = models.RawDataReceivedEvent(
            raw_data=RawDataFactory(boefje_meta=boefje_meta, mime_types=[{"value": "text/plain"}]),
            organization=self.organisation.id,
            created_at=datetime.datetime.now(),
        ).model_dump_json()

        self.mock_get_normalizers_for_mime_type.return_value = [NormalizerFactory()]
        self.mock_has_normalizer_permission_to_run.return_value = True
        self.mock_has_normalizer_task_started_running.side_effect = Exception("Something went wrong")

        # Act
        self.scheduler.process_raw_data(raw_data_event)

        # Task should not be on priority queue
        self.assertEqual(0, self.scheduler.queue.qsize())

    def test_process_raw_data_item_on_queue(self):
        # Arrange
        ooi = OOIFactory(scan_profile=ScanProfileFactory(level=0))
        boefje = BoefjeFactory()
        boefje_meta = BoefjeMetaFactory(boefje=boefje, input_ooi=ooi.primary_key)

        raw_data_event1 = models.RawDataReceivedEvent(
            raw_data=RawDataFactory(boefje_meta=boefje_meta, mime_types=[{"value": "text/plain"}]),
            organization=self.organisation.id,
            created_at=datetime.datetime.now(),
        ).model_dump_json()

        raw_data_event2 = models.RawDataReceivedEvent(
            raw_data=RawDataFactory(boefje_meta=boefje_meta, mime_types=[{"value": "text/plain"}]),
            organization=self.organisation.id,
            created_at=datetime.datetime.now(),
        ).model_dump_json()

        # Mocks
        self.mock_get_normalizers_for_mime_type.return_value = [NormalizerFactory()]

        # Act
        self.scheduler.process_raw_data(raw_data_event1)
        self.scheduler.process_raw_data(raw_data_event2)

        # Task should be on priority queue (only one)
        task_pq = self.scheduler.queue.peek(0)
        self.assertEqual(1, self.scheduler.queue.qsize())

        # Task should be in datastore, and queued
        task_db = self.mock_ctx.datastores.task_store.get_task(task_pq.id)
        self.assertEqual(task_db.id, task_pq.id)
        self.assertEqual(task_db.status, models.TaskStatus.QUEUED)

    def test_process_raw_data_error_mimetype(self):
        # Arrange
        scan_profile = ScanProfileFactory(level=0)
        ooi = OOIFactory(scan_profile=scan_profile)
        boefje = BoefjeFactory()
        boefje_task = models.BoefjeTask(boefje=boefje, input_ooi=ooi.primary_key, organization=self.organisation.id)

        task = functions.create_task(
            scheduler_id=self.scheduler.scheduler_id, data=boefje_task, organisation=self.organisation.id
        )
        self.mock_ctx.datastores.task_store.create_task(task)

        boefje_meta = BoefjeMetaFactory(boefje=boefje, input_ooi=ooi.primary_key)

        raw_data_event = models.RawDataReceivedEvent(
            raw_data=RawDataFactory(boefje_meta=boefje_meta, mime_types=[{"value": "error/unknown"}]),
            organization=self.organisation.id,
            created_at=datetime.datetime.now(),
        ).model_dump_json()

        # Act
        self.scheduler.process_raw_data(raw_data_event)

        # Task should not be on priority queue
        self.assertEqual(0, self.scheduler.queue.qsize())

    def test_process_raw_data_queue_full(self):
        events = []
        for _ in range(0, 2):
            # Arrange
            scan_profile = ScanProfileFactory(level=0)
            ooi = OOIFactory(scan_profile=scan_profile)
            boefje = BoefjeFactory()
            boefje_task = models.BoefjeTask(boefje=boefje, input_ooi=ooi.primary_key, organization=self.organisation.id)
            task = functions.create_task(
                scheduler_id=self.scheduler.scheduler_id, data=boefje_task, organisation=self.organisation.id
            )
            self.mock_ctx.datastores.task_store.create_task(task)

            boefje_meta = BoefjeMetaFactory(boefje=boefje, input_ooi=ooi.primary_key)

            raw_data_event = models.RawDataReceivedEvent(
                raw_data=RawDataFactory(boefje_meta=boefje_meta, mime_types=[{"value": "text/plain"}]),
                organization=self.organisation.id,
                created_at=datetime.datetime.now(),
            ).model_dump_json()

            events.append(raw_data_event)

        self.scheduler.queue.maxsize = 1
        self.scheduler.max_tries = 1

        # Mocks
        self.mock_get_normalizers_for_mime_type.return_value = [NormalizerFactory()]

        # Act
        self.scheduler.process_raw_data(events[0])

        # Assert
        self.assertEqual(1, self.scheduler.queue.qsize())

        with capture_logs() as cm:
            self.scheduler.process_raw_data(events[1])

        self.assertIn("Queue is full", cm[-1].get("event"))
        self.assertEqual(1, self.scheduler.queue.qsize())
