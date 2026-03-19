from ipaddress import IPv4Address, IPv6Address
from pathlib import Path

from pydantic import AnyUrl

from boefjes.local.runner import LocalNormalizerJobRunner
from boefjes.normalizer_models import NormalizerResults
from boefjes.worker.job_models import NormalizerMeta
from boefjes.worker.repository import LocalPluginRepository
from octopoes.models import Reference
from tests.loading import get_dummy_data

TEST_DECLARATIONS_DATA = (
    b"["
    b'{"ooi": {"object_type": "Network", "scan_profile": null, "user_id": null\
    , "primary_key": "Network|net1", "name": "net1"}},'
    b'{"ooi": {"object_type": "Network", "scan_profile": null, "user_id": null\
    , "primary_key": "Network|net2", "name": "net2"}}'
    b"]"
)
CSV_EXAMPLES = [
    # hostname
    b"name,network\nexample.com,internet",
    # hostname without network
    b"name\nexample.net",
    # ipv4s
    b"""address,network
1.1.1.1,internet
2.2.2.2,internet
3.3.3.3,darknet""",
    # ipv6s
    b"""address,network
FE80:CD00:0000:0CDE:1257:0000:211E:729C,internet
FE80:CD00:0000:0CDE:1257:0000:211E:729D,darknet""",
    # urls
    b"""network,raw
internet,https://example.com/
darknet,https://openkat.nl/""",
    # url without network
    b"raw\nhttps://example.com/",
]


def test_parse_manual_declarations(normalizer_runner):
    meta = NormalizerMeta.model_validate_json(get_dummy_data("manual-ooi.json"))
    output = normalizer_runner.run(meta, TEST_DECLARATIONS_DATA)

    assert len(output.declarations) == 2
    assert len(output.observations) == 0

    assert output.declarations[0].ooi.dict() == {
        "name": "net1",
        "object_type": "Network",
        "primary_key": "Network|net1",
        "scan_profile": None,
        "user_id": None,
    }
    assert output.declarations[1].ooi.dict() == {
        "name": "net2",
        "object_type": "Network",
        "primary_key": "Network|net2",
        "scan_profile": None,
        "user_id": None,
    }


def test_parse_manual_hostname_csv(normalizer_runner):
    meta, output, runner = check_network_created(normalizer_runner, 0)

    assert len(output.declarations) == 2
    assert output.declarations[1].ooi.dict() == {
        "dns_zone": None,
        "name": "example.com",
        "network": Reference("Network|internet"),
        "object_type": "Hostname",
        "primary_key": "Hostname|internet|example.com",
        "registered_domain": None,
        "scan_profile": None,
        "user_id": None,
    }

    meta, output, runner = check_network_created(normalizer_runner, 1)

    assert len(output.declarations) == 2
    assert output.declarations[1].ooi.dict() == {
        "dns_zone": None,
        "name": "example.net",
        "network": Reference("Network|internet"),
        "object_type": "Hostname",
        "primary_key": "Hostname|internet|example.net",
        "registered_domain": None,
        "scan_profile": None,
        "user_id": None,
    }


def test_parse_manual_ip_csv(normalizer_runner):
    meta, output, runner = check_network_created(normalizer_runner, 2)
    assert len(output.declarations) == 6
    assert output.declarations[1].ooi.model_dump() == {
        "address": IPv4Address("1.1.1.1"),
        "netblock": None,
        "network": Reference("Network|internet"),
        "object_type": "IPAddressV4",
        "primary_key": "IPAddressV4|internet|1.1.1.1",
        "scan_profile": None,
        "user_id": None,
    }

    meta, output, runner = check_network_created(normalizer_runner, 3)
    assert output.declarations[1].ooi.model_dump() == {
        "address": IPv6Address("fe80:cd00:0:cde:1257:0:211e:729c"),
        "netblock": None,
        "network": Reference("Network|internet"),
        "object_type": "IPAddressV6",
        "primary_key": "IPAddressV6|internet|fe80:cd00:0:cde:1257:0:211e:729c",
        "scan_profile": None,
        "user_id": None,
    }


def test_parse_url_csv(normalizer_runner):
    meta, output, runner = check_network_created(normalizer_runner, 4)
    assert len(output.declarations) == 4

    assert output.declarations[1].ooi.model_dump() == {
        "network": Reference("Network|internet"),
        "object_type": "URL",
        "primary_key": "URL|internet|https://example.com/",
        "raw": AnyUrl("https://example.com/"),
        "scan_profile": None,
        "user_id": None,
        "web_url": None,
    }

    meta, output, runner = check_network_created(normalizer_runner, 5)
    assert len(output.declarations) == 2
    assert output.declarations[1].ooi.dict() == {
        "network": Reference("Network|internet"),
        "object_type": "URL",
        "primary_key": "URL|internet|https://example.com/",
        "raw": AnyUrl("https://example.com/"),
        "scan_profile": None,
        "user_id": None,
        "web_url": None,
    }


def check_network_created(
    normalizer_runner, csv_idx: int
) -> tuple[NormalizerMeta, NormalizerResults, LocalNormalizerJobRunner]:
    meta = NormalizerMeta.model_validate_json(get_dummy_data("manual-csv.json"))
    local_repository = LocalPluginRepository(Path(__file__).parent.parent / "boefjes" / "plugins")
    runner = LocalNormalizerJobRunner(local_repository)
    output = normalizer_runner.run(meta, CSV_EXAMPLES[csv_idx])

    assert len(output.observations) == 0
    assert output.declarations[0].ooi.dict() == {
        "name": "internet",
        "object_type": "Network",
        "primary_key": "Network|internet",
        "scan_profile": None,
        "user_id": None,
    }

    return meta, output, runner
