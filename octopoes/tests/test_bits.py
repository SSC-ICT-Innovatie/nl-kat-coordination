import json
from pathlib import Path

from bits.https_availability.https_availability import run as run_https_availability
from bits.oois_in_headers.oois_in_headers import run as run_oois_in_headers

from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.network import IPAddressV4, IPPort
from octopoes.models.ooi.web import URL, HTTPHeader, HTTPHeaderURL


def test_url_extracted_by_oois_in_headers_url():
    header = HTTPHeader(
        resource="resource|internet|ip|protocol|port|protocol|internet|hostname|protocol|internet|hostname|port|location",
        key="Location",
        value="https://www.example.com/",
    )

    results = list(run_oois_in_headers(header, [], {}))

    url = results[0]
    assert isinstance(url, URL)
    assert str(url.raw) == "https://www.example.com/"
    assert url.network == "Network|internet"

    http_header_url = results[1]
    assert isinstance(http_header_url, HTTPHeaderURL)
    assert http_header_url.header == header.reference
    assert http_header_url.url == url.reference


def test_url_extracted_by_oois_in_headers_relative_path(http_resource_https):
    header = HTTPHeader(resource=http_resource_https.reference, key="Location", value="script.php")

    results = list(run_oois_in_headers(header, [], {}))

    url = results[0]
    assert isinstance(url, URL)
    assert str(url.raw) == "https://example.com/script.php"
    assert url.network == "Network|internet"

    http_header_url = results[1]
    assert isinstance(http_header_url, HTTPHeaderURL)
    assert http_header_url.header == header.reference
    assert http_header_url.url == url.reference


def test_finding_generated_when_443_not_open_and_80_is_open():
    port_80 = IPPort(address="address|fake", protocol="tcp", port=80)
    input_ooi = IPAddressV4(address="192.0.2.1", network="Network|internet")
    results = list(run_https_availability(input_ooi, [port_80], {}))
    finding_type = results[0]
    assert isinstance(finding_type, KATFindingType)
    finding = results[-1]
    assert isinstance(finding, Finding)
    # The description lives on the finding type (hydrated from the
    # registry by the kat-finding-types normalizer), never on the Finding.
    assert finding.description is None
    assert str(finding.finding_type) == "KATFindingType|KAT-HTTPS-NOT-AVAILABLE"
    # The finding binds to the address: there is no website object when
    # HTTPS is unavailable.
    assert str(finding.ooi) == "IPAddressV4|internet|192.0.2.1"


def test_https_not_available_is_described_in_the_registry():
    """A finding type a bit emits must be described in the static catalog:
    the kat-finding-types normalizer hydrates the stored object from it,
    and the description is undefined otherwise."""
    registry = json.loads(
        (
            Path(__file__).parent.parent.parent / "boefjes/boefjes/plugins/kat_kat_finding_types/kat_finding_types.json"
        ).read_text()  # codespell-ignore
    )

    entry = registry["KAT-HTTPS-NOT-AVAILABLE"]
    assert entry["description"]
    assert entry["impact"]
    assert entry["recommendation"]
    assert entry["risk"] in {"low", "medium", "high", "critical", "recommendation"}
