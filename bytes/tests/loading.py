import datetime
import json
from datetime import timezone
from typing import Any
from uuid import UUID

from bytes.config import BASE_DIR
from bytes.models import Boefje, BoefjeMeta, MimeType, Normalizer, NormalizerMeta, RawData, RawDataMeta


def load_stub(relative_path: str) -> dict[str, Any]:
    full_path = BASE_DIR / "tests" / "stubs" / relative_path

    return dict(json.loads(full_path.read_text()))


def load_stub_raw(relative_path: str) -> bytes:
    full_path = BASE_DIR / "tests" / "stubs" / relative_path

    return full_path.read_bytes()


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


def get_normalizer_meta(raw_file_id: UUID = UUID("2c9f47db-dfca-4928-b29f-368e64b3c779")) -> NormalizerMeta:
    return NormalizerMeta(
        id=UUID("203eedee-a590-43e1-8f80-6d18ffe529f5"),
        raw_data=get_raw_data_meta(raw_file_id),
        normalizer=Normalizer(id="kat_test.main"),
        started_at=datetime.datetime(year=1001, month=10, day=10, hour=10, minute=10, second=10, tzinfo=timezone.utc),
        ended_at=datetime.datetime(year=1001, month=10, day=10, hour=10, minute=10, second=12, tzinfo=timezone.utc),
    )


def get_raw_data() -> RawData:
    return RawData(
        value=b"KAT for president",
        mime_types=[MimeType(value="boefje_id/test"), MimeType(value="text/plain")],
        boefje_meta=get_boefje_meta(),
    )


def get_raw_data_meta(raw_file_id: UUID = UUID("2c9f47db-dfca-4928-b29f-368e64b3c779")) -> RawDataMeta:
    raw_data = get_raw_data()

    return RawDataMeta(id=raw_file_id, boefje_meta=raw_data.boefje_meta, mime_types=raw_data.mime_types)
