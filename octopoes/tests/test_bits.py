from nibbles.https_availability.https_availability import nibble as run_https_availability
from nibbles.oois_in_headers.oois_in_headers import nibble as run_oois_in_headers

from octopoes.models.ooi.config import Config
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.network import IPPort
from octopoes.models.ooi.web import URL, HTTPHeader, HTTPHeaderURL, Website


def test_url_extracted_by_oois_in_headers_url():
    header = HTTPHeader(
        resource="resource|internet|ip|protocol|port|protocol|internet|hostname|protocol|internet|hostname|port|location",
        key="Location",
        value="https://www.example.com/",
    )

    results = list(run_oois_in_headers(header, Config(ooi=header.reference, bit_id="oois-in-headers", config={})))

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

    results = list(run_oois_in_headers(header, Config(ooi=header.reference, bit_id="oois-in-headers", config={})))

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
    website = Website(ip_service="service|fake", hostname="hostname|fake")
    results = list(run_https_availability(None, port_80, website, 0))
    finding = [result for result in results if isinstance(result, Finding)][0]
    assert finding.description == "HTTP port is open, but HTTPS port is not open"
    katfindingtype = [result for result in results if not isinstance(result, Finding)][0]
    assert isinstance(katfindingtype, KATFindingType)
