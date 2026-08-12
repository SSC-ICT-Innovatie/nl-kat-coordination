import datetime
from datetime import timezone
from uuid import UUID

from boefjes.config import BASE_DIR
from boefjes.worker.interfaces import Task, TaskStatus
from boefjes.worker.job_models import Boefje, BoefjeMeta, Normalizer, NormalizerMeta, RawDataMeta


def get_dummy_data(filename: str) -> bytes:
    path = BASE_DIR.parent / "tests" / "examples" / filename
    return path.read_bytes()


def get_task(
    task_id: UUID = UUID("a64d755b-6c23-44ab-8de6-8d144c448ab3"), boefje_id: str = "kat_test.main"
) -> BoefjeMeta:
    return Task(
        id=task_id,
        data=get_boefje_meta(boefje_id=boefje_id),
        schedule_id="test",
        scheduler_id="test",
        priority=1,
        status=TaskStatus.RUNNING,
        type="boefje",
        organisation="test",
        created_at=datetime.datetime(1000, 10, 10, 10, 10, 10, tzinfo=timezone.utc),
        modified_at=datetime.datetime(1000, 10, 10, 10, 10, 11, tzinfo=timezone.utc),
    )


def get_boefje_meta(
    meta_id: UUID = UUID("d63d755b-6c23-44ab-8de6-8d144c448a71"),
    boefje_id: str = "kat_test.main",
    input_ooi: str | None = "Hostname|internet|test.org",
) -> BoefjeMeta:
    return BoefjeMeta(
        id=meta_id,
        boefje=Boefje(id=boefje_id, version="1"),
        input_ooi=input_ooi,
        arguments={"domain": "test.org"},
        organization="test",
        started_at=datetime.datetime(1000, 10, 10, 10, 10, 10, tzinfo=timezone.utc),
        ended_at=datetime.datetime(1000, 10, 10, 10, 10, 11, tzinfo=timezone.utc),
    )


def get_normalizer_meta(
    boefje_meta: BoefjeMeta = get_boefje_meta(), raw_file_id: UUID = UUID("2c9f47db-dfca-4928-b29f-368e64b3c779")
) -> NormalizerMeta:
    return NormalizerMeta(
        id=UUID("203eedee-a590-43e1-8f80-6d18ffe529f5"),
        raw_data=get_raw_data_meta(raw_file_id, boefje_meta),
        normalizer=Normalizer(id="kat_test.main"),
        started_at=datetime.datetime(1001, 10, 10, 10, 10, 10, tzinfo=timezone.utc),
        ended_at=datetime.datetime(1001, 10, 10, 10, 10, 12, tzinfo=timezone.utc),
    )


def get_raw_data_meta(
    raw_file_id: UUID = UUID("2c9f47db-dfca-4928-b29f-368e64b3c779"), boefje_meta: BoefjeMeta = get_boefje_meta()
) -> RawDataMeta:
    return RawDataMeta(
        id=raw_file_id, boefje_meta=boefje_meta, mime_types=[{"value": "boefje_id/test"}, {"value": "text/plain"}]
    )
