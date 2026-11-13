from tests.factories.boefje import BoefjeMetaFactory
from tests.factories.normalizer import NormalizerFactory
from tests.factories.raw_data import RawDataFactory

from scheduler.models.task import NormalizerTask


def test_normalizer_task_hash_differs_per_raw_file():
    """Two raw files of one boefje run that trigger the same normalizer must produce distinct
    tasks, otherwise the second one is deduplicated on the queue (#5581)."""
    boefje_meta = BoefjeMetaFactory()
    normalizer = NormalizerFactory()

    task_one = NormalizerTask(normalizer=normalizer, raw_data=RawDataFactory(boefje_meta=boefje_meta))
    task_two = NormalizerTask(normalizer=normalizer, raw_data=RawDataFactory(boefje_meta=boefje_meta))

    assert task_one.hash != task_two.hash


def test_normalizer_task_hash_stable_for_same_raw_file():
    boefje_meta = BoefjeMetaFactory()
    normalizer = NormalizerFactory()
    raw_data = RawDataFactory(boefje_meta=boefje_meta)

    assert NormalizerTask(normalizer=normalizer, raw_data=raw_data).hash == NormalizerTask(
        normalizer=normalizer, raw_data=raw_data
    ).hash
