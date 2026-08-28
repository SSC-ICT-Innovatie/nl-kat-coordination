import os

import alembic.config
import pytest
from psycopg2.extras import execute_values
from sqlalchemy.orm import Session, sessionmaker

from boefjes.sql.db import SQL_BASE, get_engine

pytestmark = pytest.mark.skipif(os.environ.get("CI") != "1", reason="Needs a CI database.")


@pytest.fixture
def migration_f9de6eb7824b(local_repository) -> Session:
    alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "upgrade", "head"])
    # To reset autoincrement ids
    alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "downgrade", "base"])
    # Set state to revision f9de6eb7824b
    alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "upgrade", "f9de6eb7824b"])

    engine = get_engine()
    session = sessionmaker(bind=engine)()

    dns_records = local_repository.by_id("dns-records").boefje
    nmap_udp = local_repository.by_id("nmap-udp").boefje
    entries = [
        (
            boefje.id,
            boefje.name,
            boefje.description,
            str(boefje.scan_level),
            list(sorted(boefje.consumes)),
            list(sorted(boefje.produces)),
            ["RECORD_TYPES", "REMOTE_NS"],
            boefje.oci_image,
            boefje.oci_arguments,
            boefje.version,
        )
        for boefje in [dns_records, nmap_udp]
    ]

    query = """INSERT INTO boefje (plugin_id, name, description, scan_level, consumes, produces, environment_keys,
            oci_image, oci_arguments, version) values %s"""

    connection = session.connection()
    with connection.begin():
        execute_values(connection.connection.cursor(), query, entries)

    session.commit()

    yield session
    session.commit()

    alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "upgrade", "head"])

    engine.execute(";".join([f"TRUNCATE TABLE {t} CASCADE" for t in SQL_BASE.metadata.tables]))


def test_fail_on_wrong_plugin_ids(migration_f9de6eb7824b):
    session = migration_f9de6eb7824b
    assert session.execute("SELECT * from boefje").fetchall() == [
        (
            1,
            "dns-records",
            None,
            "DNS records",
            "Fetch the DNS record(s) of a hostname.",
            "1",
            ["Hostname"],
            ["boefje/dns-records"],
            ["RECORD_TYPES", "REMOTE_NS"],
            "ghcr.io/minvws/openkat/generic:latest",
            ["kat_dns.main"],
            None,
            False,
        ),
        (
            2,
            "nmap-udp",
            None,
            "Nmap UDP",
            "Defaults to top 250 UDP ports. Includes service detection.",
            "2",
            ["IPAddressV4", "IPAddressV6"],
            ["boefje/nmap-udp"],
            ["RECORD_TYPES", "REMOTE_NS"],
            "ghcr.io/minvws/openkat/nmap:latest",
            ["--open", "-T4", "-Pn", "-r", "-v10", "-sV", "-sU"],
            None,
            False,
        ),
    ]

    session.close()

    alembic.config.main(argv=["--config", "/app/boefjes/boefjes/alembic.ini", "upgrade", "5be152459a7b"])

    schema_dns = {
        "title": "Arguments",
        "type": "object",
        "properties": {
            "RECORD_TYPES": {
                "title": "RECORD_TYPES",
                "type": "string",
                "description": "List of comma separated DNS record types to query for.",
                "default": "A,AAAA,CAA,CERT,RP,SRV,TXT,MX,NS,CNAME,DNAME",
            },
            "REMOTE_NS": {
                "title": "REMOTE_NS",
                "maxLength": 45,
                "type": "string",
                "description": "The IP address of the DNS resolver you want to use.",
                "default": "1.1.1.1",
            },
        },
    }

    schema_udp = {
        "title": "Arguments",
        "type": "object",
        "properties": {
            "TOP_PORTS_UDP": {
                "title": "TOP_PORTS_UDP",
                "type": "integer",
                "minimum": 1,
                "maximum": 65535,
                "description": "Scan TOP_PORTS_UDP most common ports. Defaults to 250.",
            }
        },
        "required": [],
    }

    assert session.execute("SELECT * from boefje").fetchall() == [
        (
            1,
            "dns-records",
            None,
            "DNS records",
            "Fetch the DNS record(s) of a hostname.",
            "1",
            ["Hostname"],
            ["boefje/dns-records"],
            ["RECORD_TYPES", "REMOTE_NS"],
            "ghcr.io/minvws/openkat/generic:latest",
            ["kat_dns.main"],
            None,
            False,
            schema_dns,
        ),
        (
            2,
            "nmap-udp",
            None,
            "Nmap UDP",
            "Defaults to top 250 UDP ports. Includes service detection.",
            "2",
            ["IPAddressV4", "IPAddressV6"],
            ["boefje/nmap-udp"],
            ["RECORD_TYPES", "REMOTE_NS"],
            "ghcr.io/minvws/openkat/nmap:latest",
            ["--open", "-T4", "-Pn", "-r", "-v10", "-sV", "-sU"],
            None,
            False,
            schema_udp,
        ),
    ]
