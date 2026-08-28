from nibbles.missing_headers.missing_headers import nibble as run

from octopoes.models.ooi.web import HTTPHeader


def test_https_hsts(http_resource_https):
    headers = [
        HTTPHeader(resource=http_resource_https.reference, key="Content-Type", value="text/html"),
        HTTPHeader(
            resource=http_resource_https.reference,
            key="Strict-Transport-Security",
            value="max-age=31536000; includeSubDomains",
        ),
    ]

    results = list(run(http_resource_https, headers))
    hsts_findings = [r for r in results if r.object_type == "Finding" and r.finding_type.natural_key == "KAT-NO-HSTS"]

    assert not hsts_findings


def test_https_no_hsts(http_resource_https):
    headers = [HTTPHeader(resource=http_resource_https.reference, key="Content-Type", value="text/html")]

    results = list(run(http_resource_https, headers))
    hsts_findings = [r for r in results if r.object_type == "Finding" and r.finding_type.natural_key == "KAT-NO-HSTS"]

    assert len(hsts_findings) == 1


def test_http_no_hsts(http_resource_http):
    headers = [HTTPHeader(resource=http_resource_http.reference, key="Content-Type", value="text/html")]

    results = list(run(http_resource_http, headers))
    hsts_findings = [r for r in results if r.object_type == "Finding" and r.finding_type.natural_key == "KAT-NO-HSTS"]

    assert not hsts_findings


def test_deprecated_header(http_resource_https):
    headers = [HTTPHeader(resource=http_resource_https.reference, key="x-forwarded-for", value="DENY")]

    results = list(run(http_resource_https, headers))
    deprecated_headers_findings = [
        r for r in results if r.object_type == "Finding" and r.finding_type.natural_key == "KAT-NONSTANDARD-HEADERS"
    ]

    assert len(deprecated_headers_findings) == 1
