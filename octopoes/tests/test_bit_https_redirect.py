from bits.https_redirect.https_redirect import run

from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import HostnameHTTPURL, HTTPHeader

NETWORK = Reference.from_str("Network|internet")
HOSTNAME = Reference.from_str("Hostname|internet|example.com")


def _http_url(scheme: str = "http", port: int = 80) -> HostnameHTTPURL:
    return HostnameHTTPURL(netloc=HOSTNAME, path="/", scheme=scheme, network=NETWORK, port=port)


def test_https_redirect_finding_when_http_without_location_header():
    url = _http_url()
    headers = [HTTPHeader(resource=url.reference, key="Content-Type", value="text/html")]

    results = list(run(url, headers, {}))

    finding_types = [r for r in results if isinstance(r, KATFindingType)]
    findings = [r for r in results if isinstance(r, Finding)]
    assert len(finding_types) == 1
    assert finding_types[0].id == "KAT-NO-HTTPS-REDIRECT"
    assert len(findings) == 1
    assert findings[0].ooi == url.reference


def test_https_redirect_no_finding_when_location_header_present():
    url = _http_url()
    headers = [
        HTTPHeader(resource=url.reference, key="Content-Type", value="text/html"),
        HTTPHeader(resource=url.reference, key="Location", value="https://example.com/"),
    ]

    results = list(run(url, headers, {}))

    assert not [r for r in results if isinstance(r, Finding)]


def test_https_redirect_location_header_case_insensitive():
    url = _http_url()
    headers = [HTTPHeader(resource=url.reference, key="location", value="https://example.com/")]

    results = list(run(url, headers, {}))

    assert not [r for r in results if isinstance(r, Finding)]


def test_https_redirect_no_finding_for_https_url():
    url = _http_url(scheme="https", port=443)
    headers = [HTTPHeader(resource=url.reference, key="Content-Type", value="text/html")]

    results = list(run(url, headers, {}))

    assert not [r for r in results if isinstance(r, Finding)]


def test_https_redirect_no_finding_when_no_headers():
    url = _http_url()

    results = list(run(url, [], {}))

    assert results == []
