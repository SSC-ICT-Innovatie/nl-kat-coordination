import os

import alembic.config
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from boefjes.sql.config_storage import SQLConfigStorage, create_encrypter
from boefjes.sql.db import SQL_BASE, get_engine

pytestmark = pytest.mark.skipif(os.environ.get("CI") != "1", reason="Needs a CI database.")


@pytest.fixture
def migration_6f99834a4a5a() -> Session:
    alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "upgrade", "head"])
    # To reset autoincrement ids
    alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "downgrade", "base"])
    # Set state to revision 6f99834a4a5a
    alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "upgrade", "6f99834a4a5a"])

    engine = get_engine()
    session = sessionmaker(bind=engine)()

    query = f"""INSERT INTO organisation (id, name) values {','.join(map(str, [
        ("dev1", "Test 1 "),
        ("dev2", "Test 2 "),
    ]))}"""  # noqa: S608
    session.get_bind().execute(text(query))

    encrypter = create_encrypter()
    entries = [
        (1, encrypter.encode('{"key1": "val1"}'), "dns-records", 1),
        (2, encrypter.encode('{"key1": "val1", "key2": "val2"}'), "dns-records", 2),
        (3, encrypter.encode('{"key2": "val2", "key3": "val3"}'), "nmap", 1),
    ]
    query = f"INSERT INTO settings (id, values, plugin_id, organisation_pk) values {','.join(map(str, entries))}"  # noqa: S608

    engine.execute(text(query))

    entries = [(1, "dns-records", True, 1), (2, "nmap-udp", True, 1)]
    query = f"INSERT INTO plugin_state (id, plugin_id, enabled, organisation_pk) values {','.join(map(str, entries))}"  # noqa: S608
    engine.execute(text(query))

    yield session
    session.commit()

    alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "upgrade", "head"])

    engine.execute(";".join([f"TRUNCATE TABLE {t} CASCADE" for t in SQL_BASE.metadata.tables]))


def test_fail_on_wrong_plugin_ids(migration_6f99834a4a5a):
    session = migration_6f99834a4a5a

    encrypter = create_encrypter()
    entries = [
        (4, encrypter.encode('{"key2": "val2", "key3": "val3"}'), "test-unknown-plugin-id", 1),
        (5, encrypter.encode('{"key1": "val1"}'), "kat_nmap_normalize", 2),
    ]
    query = f"INSERT INTO settings (id, values, plugin_id, organisation_pk) values {','.join(map(str, entries))}"  # noqa: S608
    session.execute(text(query))
    session.commit()
    session.close()

    with pytest.raises(Exception) as ctx:
        alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "upgrade", "f9de6eb7824b"])

    assert "Settings for normalizer or bit found: kat_nmap_normalize" in str(ctx.value)

    session.execute(text("DELETE FROM settings WHERE id = 5"))  # Fix normalizer setting
    session.commit()
    session.close()

    with pytest.raises(Exception) as ctx:
        alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "upgrade", "f9de6eb7824b"])

    assert "Invalid plugin id found: test-unknown-plugin-id" in str(ctx.value)

    session.execute(text("DELETE FROM settings WHERE id = 4"))  # Fix unknown plugin
    session.commit()
    session.close()

    alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "upgrade", "f9de6eb7824b"])

    assert session.execute(text("SELECT id FROM boefje WHERE plugin_id = 'dns-records'")).fetchall() == [(2,)]
    session.commit()
    session.close()

    config_storage = SQLConfigStorage(session, encrypter)

    with config_storage:
        assert config_storage.get_all_settings("dev1", "dns-records") == {"key1": "val1"}
        assert config_storage.get_all_settings("dev1", "nmap-udp") == {}
        assert config_storage.get_all_settings("dev2", "dns-records") == {"key1": "val1", "key2": "val2"}

        assert config_storage.is_enabled_by_id("dns-records", "dev1")
        assert config_storage.is_enabled_by_id("nmap-udp", "dev1")

    session.commit()
    session.close()


def test_downgrade(migration_6f99834a4a5a):
    session = migration_6f99834a4a5a

    # No need to also create a Boefje entry, the seeded settings and migrations take care of that and
    alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "upgrade", "f9de6eb7824b"])
    alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "downgrade", "-1"])

    encrypter = create_encrypter()
    all_settings = list(session.execute(text("select * from settings")).fetchall())
    session.commit()
    session.close()
    assert {(encrypter.decode(x[1]) if x[1] != "{}" else "{}", x[2], x[3]) for x in all_settings} == {
        ('{"key1": "val1"}', "dns-records", 1),
        ('{"key1": "val1", "key2": "val2"}', "dns-records", 2),
        ('{"key2": "val2", "key3": "val3"}', "nmap", 1),
        ("{}", "nmap-udp", 1),
    }
