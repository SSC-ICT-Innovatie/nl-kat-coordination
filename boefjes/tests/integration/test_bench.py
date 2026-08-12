import json
import uuid
from pathlib import Path

import pytest
from tools.upgrade_v1_17_0 import upgrade

from boefjes.clients.bytes_client import BytesAPIClient
from boefjes.config import BASE_DIR
from boefjes.sql.organisation_storage import SQLOrganisationStorage
from boefjes.worker.models import Organisation
from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models import Reference
from octopoes.models.origin import OriginType
from tests.conftest import seed_system
from tests.loading import get_boefje_meta, get_normalizer_meta


@pytest.mark.skipif("not os.getenv('DATABASE_MIGRATION')")
@pytest.mark.slow
def test_migration(
    octopoes_api_connector: OctopoesAPIConnector,
    bytes_client: BytesAPIClient,
    organisation_storage: SQLOrganisationStorage,
    valid_time,
):
    octopoes_api_connector.session._timeout.connect = 60
    octopoes_api_connector.session._timeout.read = 60

    # Create an organisation that does not exist in Octopoes
    organisation_storage.create(Organisation(id="test2", name="Test 2"))

    iterations = 30
    cache_path = Path(BASE_DIR.parent / ".ci" / f".cache_{iterations}.json")
    hostname_range = range(0, iterations)

    if cache_path.exists():
        export = json.load(cache_path.open())
        exported = json.dumps(export)
    else:
        for x in hostname_range:
            seed_system(
                octopoes_api_connector,
                valid_time,
                test_hostname=f"{x}.com",
                test_ip=f"192.0.{x % 7}.{x % 13}",
                test_ipv6=f"{x % 7}e4d:64a2:cb49:bd48:a1ba:def3:d15d:{x % 5}230",
                method="kat_nmap_normalize" if x % 3 == 0 else "kat_dns_normalize",  # 30% of the origins need Bytes
            )

        export = []

        # Drop the source method field to test the migration
        for tx in octopoes_api_connector.export_all():
            if "txOps" in tx:
                ops = []
                for tx_op in tx["txOps"]:
                    if "source_method" in tx_op[1]:
                        del tx_op[1]["source_method"]

                    ops.append(tx_op)

                tx["txOps"] = ops

            export.append(tx)

        exported = json.dumps(export)
        cache_path.write_text(exported)

    octopoes_api_connector.import_new(exported)

    raw = b"1234567890"
    bytes_client.login()

    for method in ["kat_nmap_normalize", "kat_dns_normalize"]:
        for origin in octopoes_api_connector.list_origins(
            valid_time, method=method, origin_type=OriginType.OBSERVATION
        ):
            boefje_id = "boefje_" + method

            if "3.com" in origin.source:  # create one udp scan
                boefje_id = "boefje_udp"

            boefje_meta = get_boefje_meta(uuid.uuid4(), boefje_id=boefje_id)
            bytes_client.save_boefje_meta(boefje_meta)
            raw_data_id = bytes_client.save_raw(boefje_meta.id, raw, {})

            normalizer_meta = get_normalizer_meta(boefje_meta, raw_data_id)
            normalizer_meta.id = origin.task_id
            normalizer_meta.normalizer.id = method

            bytes_client.save_normalizer_meta(normalizer_meta)

    total_oois = octopoes_api_connector.list_objects(set(), valid_time).count
    total_processed, total_failed = upgrade(organisation_storage, valid_time)

    assert total_processed == len(hostname_range)
    assert total_failed == 0

    observation = octopoes_api_connector.list_origins(
        valid_time, source=Reference.from_str("Hostname|test|0.com"), origin_type=OriginType.OBSERVATION
    )[0]
    assert observation.method == "kat_nmap_normalize"
    assert observation.source_method == "boefje_kat_nmap_normalize"

    observation = octopoes_api_connector.list_origins(
        valid_time, source=Reference.from_str("Hostname|test|1.com"), origin_type=OriginType.OBSERVATION
    )[0]
    assert observation.method == "kat_dns_normalize"
    assert observation.source_method == "dns-records"  # the logic has found the right boefje id

    observation = octopoes_api_connector.list_origins(
        valid_time, source=Reference.from_str("Hostname|test|3.com"), origin_type=OriginType.OBSERVATION
    )[0]
    assert observation.method == "kat_nmap_normalize"
    assert observation.source_method == "boefje_udp"

    assert octopoes_api_connector.list_objects(set(), valid_time).count == total_oois


@pytest.mark.slow
def test_plugins_bench(plugin_service, organisation):
    plugin_service.get_all(organisation.id)
