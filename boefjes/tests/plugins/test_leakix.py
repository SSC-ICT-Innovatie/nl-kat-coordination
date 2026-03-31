import json

from pydantic import TypeAdapter

from boefjes.plugins.kat_leakix.normalize import run
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPPort
from octopoes.models.types import OOIType
from tests.loading import get_dummy_data


def test_output():
    input_ooi = TypeAdapter(OOIType).validate_python(
        {
            "object_type": "HostnameHTTPURL",
            "network": "Network|internet",
            "scheme": "https",
            "port": 443,
            "path": "/",
            "netloc": "Hostname|internet|example.com",
        }
    )

    output = [x for x in run(input_ooi.serialize(), get_dummy_data("raw/leakix-example.com.json"))]

    assert len(output) == 170
    assert str(output) == get_dummy_data("raw/leakix-example.com-output.txt").decode().strip()


def _get_hostname_input_ooi():
    return TypeAdapter(OOIType).validate_python(
        {"object_type": "Hostname", "network": "Network|internet", "name": "example.com"}
    )


def test_strict_mode_filters_hostname_subdomains():
    """Test that strict mode only keeps events with exact hostname match."""
    input_ooi = _get_hostname_input_ooi()

    # Test data has 3 events: example.com (match), sub.example.com (no match), other.example.org (no match)
    output = list(run(input_ooi.serialize(), get_dummy_data("raw/leakix-hostname-strict.json")))

    # Only the exact "example.com" event should produce OOIs (7 per event)
    hostnames = [ooi for ooi in output if isinstance(ooi, Hostname)]
    ip_addresses = [ooi for ooi in output if isinstance(ooi, IPAddressV4)]
    ip_ports = [ooi for ooi in output if isinstance(ooi, IPPort)]

    assert len(output) == 7
    assert len(hostnames) == 1
    assert hostnames[0].name == "example.com"
    assert len(ip_addresses) == 1
    assert str(ip_addresses[0].address) == "93.184.215.14"
    assert len(ip_ports) == 1


def test_permissive_mode_keeps_all_hostname_results():
    """Test that permissive mode keeps all events including subdomains."""
    input_ooi = _get_hostname_input_ooi()

    # Load the strict test data and change search_mode to permissive
    raw_data = json.loads(get_dummy_data("raw/leakix-hostname-strict.json"))
    raw_data["search_mode"] = "permissive"

    output = list(run(input_ooi.serialize(), json.dumps(raw_data).encode()))

    # All 3 events should produce OOIs in permissive mode (7 per event)
    hostnames = [ooi for ooi in output if isinstance(ooi, Hostname)]
    ip_addresses = [ooi for ooi in output if isinstance(ooi, IPAddressV4)]

    assert len(output) == 21
    assert len(hostnames) == 3
    assert {h.name for h in hostnames} == {"example.com", "sub.example.com", "other.example.org"}
    assert len(ip_addresses) == 3
