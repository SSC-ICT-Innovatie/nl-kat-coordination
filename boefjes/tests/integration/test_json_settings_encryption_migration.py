import os

import alembic.config
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from boefjes.dependencies.encryption import NaclBoxMiddleware
from boefjes.sql.config_storage import create_encrypter
from boefjes.sql.db import SQL_BASE, get_engine

pytestmark = pytest.mark.skipif(os.environ.get("CI") != "1", reason="Needs a CI database.")


@pytest.fixture
def migration_197672984df0() -> Session:
    alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "upgrade", "head"])
    # To reset autoincrement ids
    alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "downgrade", "base"])
    # Set state to revision 197672984df0
    alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "upgrade", "197672984df0"])

    engine = get_engine()
    session = sessionmaker(bind=engine)()

    yield session
    session.commit()

    alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "upgrade", "head"])

    engine.execute(";".join([f"TRUNCATE TABLE {t} CASCADE" for t in SQL_BASE.metadata.tables]))


def test_setting_to_settings_json(migration_197672984df0):
    session = migration_197672984df0

    query = f"""INSERT INTO organisation (id, name) values {','.join(map(str, [
        ("dev1", "Test 1 "),
         ("dev2", "Test 2 "),
          ("dev3", "Test 3 "),
    ]))}"""  # noqa: S608
    session.get_bind().execute(text(query))

    encrypter = create_encrypter()
    entries = _collect_entries(encrypter)
    query = f"INSERT INTO setting (key, value, organisation_pk, plugin_id) values {','.join(map(str, entries))}"  # noqa: S608
    session.get_bind().execute(text(query))

    alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "upgrade", "cd34fdfafdaf"])

    all_settings = list(session.execute(text("select * from settings")).fetchall())
    assert {(encrypter.decode(x[1]), x[2], x[3]) for x in all_settings} == {
        ('{"key2": "val2"}', "dns-records", 2),
        ('{"key5": "val5", "key7": "val7"}', "nmap", 1),
        ('{"key4": "val4", "key6": "val6"}', "nmap", 2),
        ('{"key1": "val1", "key3": "val3"}', "dns-records", 1),
    }

    session.close()
    alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "downgrade", "-1"])

    results = session.execute(text("SELECT key, value, organisation_pk, plugin_id FROM setting")).fetchall()
    decoded_results = [(x[0], encrypter.decode(x[1]), x[2], x[3]) for x in results]
    decoded_entries = [(x[0], encrypter.decode(x[1]), x[2], x[3]) for x in entries]  # encoding changes every time.

    assert set(decoded_entries) == set(decoded_results)


def _collect_entries(encrypter: NaclBoxMiddleware):
    return [
        ("key1", encrypter.encode("val1"), 1, "dns-records"),
        ("key2", encrypter.encode("val2"), 2, "dns-records"),
        ("key3", encrypter.encode("val3"), 1, "dns-records"),
        ("key4", encrypter.encode("val4"), 2, "nmap"),
        ("key5", encrypter.encode("val5"), 1, "nmap"),
        ("key6", encrypter.encode("val6"), 2, "nmap"),
        ("key7", encrypter.encode("val7"), 1, "nmap"),
    ]
