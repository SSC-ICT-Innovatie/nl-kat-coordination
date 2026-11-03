from datetime import UTC, datetime
from uuid import uuid4

from bytes.database.db_models import BoefjeMetaInDB, RawFileInDB
from bytes.database.sql_meta_repository import to_raw_meta


def test_raw_file_name_roundtrip():
    meta_in_db = BoefjeMetaInDB(
        id=str(uuid4()),
        boefje_id="test_boefje",
        organization="_dev",
        arguments={},
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
    )
    raw_in_db = RawFileInDB(
        id=str(uuid4()),
        name="report.json",
        boefje_meta=meta_in_db,
        mime_types=["text/plain"],
    )

    assert to_raw_meta(raw_in_db).name == "report.json"
    assert to_raw_meta(RawFileInDB(id=str(uuid4()), boefje_meta=meta_in_db, mime_types=[])).name is None
