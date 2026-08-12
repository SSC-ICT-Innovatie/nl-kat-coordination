# NOTE: This file is DEPRECATED
import unittest
import uuid
from unittest import mock

from scheduler import config, models, queues, rankers, schedulers

from tests.factories import (
    BoefjeFactory,
    BoefjeMetaFactory,
    OOIFactory,
    OrganisationFactory,
    PluginFactory,
    RawDataFactory,
    ScanProfileFactory,
)
from tests.utils import profile_memory


class SimulationTestCase(unittest.TestCase):
    def setUp(self):
        self.cfg = config.settings.Settings()

        self.mock_ctx = mock.patch("scheduler.context.AppContext").start()
        self.mock_ctx.config = self.cfg

        self.organisation = OrganisationFactory()

    def create_normalizer_scheduler_for_organisation(self, organisation):
        normalizer_queue = queues.NormalizerPriorityQueue(
            pq_id=f"normalizer-{organisation.id}",
            maxsize=self.cfg.pq_maxsize,
            item_type=models.NormalizerTask,
            allow_priority_updates=True,
        )

        normalizer_ranker = rankers.NormalizerRanker(ctx=self.mock_ctx)

        return schedulers.NormalizerScheduler(
            ctx=self.mock_ctx,
            scheduler_id=organisation.id,
            queue=normalizer_queue,
            ranker=normalizer_ranker,
            organisation=organisation,
        )

    def create_boefje_scheduler_for_organisation(self, organisation):
        boefje_queue = queues.BoefjePriorityQueue(
            pq_id=f"boefje-{organisation.id}",
            maxsize=self.cfg.pq_maxsize,
            item_type=models.BoefjeTask,
            allow_priority_updates=True,
        )

        boefje_ranker = rankers.BoefjeRanker(ctx=self.mock_ctx)

        return schedulers.BoefjeScheduler(
            ctx=self.mock_ctx,
            scheduler_id=organisation.id,
            queue=boefje_queue,
            ranker=boefje_ranker,
            organisation=organisation,
        )

    @profile_memory
    @mock.patch("scheduler.context.AppContext.services.scan_profile.get_latest_object")
    @mock.patch("scheduler.context.AppContext.services.octopoes.get_random_objects")
    @mock.patch("scheduler.schedulers.BoefjeScheduler.create_tasks_for_oois")
    def test_simulation_boefje_queue(self, mock_create_tasks_for_oois, mock_get_random_objects, mock_get_latest_object):
        iterations = 1000
        oois = [OOIFactory(scan_profile=ScanProfileFactory(level=0)) for _ in range(iterations)]

        mock_get_latest_object.side_effect = oois + [None]

        mock_get_random_objects.return_value = []

        # We just create 1 task for each OOI
        mock_create_tasks_for_oois.side_effect = [
            [
                queues.PrioritizedItem(
                    0,
                    models.BoefjeTask(
                        id=uuid.uuid4(),
                        boefje=BoefjeFactory(),
                        input_ooi=ooi.primary_key,
                        organization=self.organisation.id,
                    ),
                )
            ]
            for ooi in oois
        ]

        b_scheduler = self.create_boefje_scheduler_for_organisation(self.organisation)
        b_scheduler.populate_queue()

        self.assertEqual(iterations, b_scheduler.queue.qsize())

    @profile_memory
    @mock.patch("scheduler.schedulers.NormalizerScheduler.create_tasks_for_raw_data")
    @mock.patch("scheduler.context.AppContext.services.raw_data.get_latest_raw_data")
    def test_simulation_normalizer_queue(self, mock_get_latest_raw_data, mock_create_tasks_for_raw_data):
        iterations = 1000
        raw_data = [
            RawDataFactory(
                boefje_meta=BoefjeMetaFactory(
                    boefje=PluginFactory(type="boefje", scan_level=0),
                    input_ooi=OOIFactory(scan_profile=ScanProfileFactory(level=0)).primary_key,
                )
            )
            for _ in range(iterations)
        ]

        mock_get_latest_raw_data.side_effect = raw_data + [None]

        # We just create 1 task for each raw data
        mock_create_tasks_for_raw_data.side_effect = [
            [
                queues.PrioritizedItem(
                    0,
                    models.NormalizerTask(
                        id=uuid.uuid4(), normalizer=PluginFactory(type="normalizer"), boefje_meta=raw_file.boefje_meta
                    ),
                )
            ]
            for raw_file in raw_data
        ]

        n_scheduler = self.create_normalizer_scheduler_for_organisation(self.organisation)
        n_scheduler.populate_queue()

        self.assertEqual(iterations, n_scheduler.queue.qsize())
