from bits.check_header_values.check_header_values import run

from octopoes.models import Reference
from octopoes.models.ooi.web import HTTPHeader, HTTPResource

RESOURCE = Reference.from_str("HTTPResource|Website|internet|example.com|192.0.2.1|443|https|Service|https|/")


def _resource():
    return HTTPResource(
        website=Reference.from_str("Website|internet|example.com|192.0.2.1|443|https|Service|https"),
        web_url=Reference.from_str("HostnameHTTPURL|internet|example.com|443|https|/"),
    )


def _header(key, value):
    return HTTPHeader(resource=RESOURCE, key=key, value=value)


def _findings(resource, headers):
    return [r for r in run(resource, headers, {}) if r.object_type == "Finding"]


def test_all_valid_headers_clean():
    resource = _resource()
    headers = [
        _header("X-Frame-Options", "DENY"),
        _header("X-Content-Type-Options", "nosniff"),
        _header("Referrer-Policy", "no-referrer"),
        _header("Permissions-Policy", "geolocation=(), camera=()"),
    ]
    assert _findings(resource, headers) == []


def test_xfo_allow_from_deprecated():
    resource = _resource()
    headers = [_header("X-Frame-Options", "ALLOW-FROM https://evil.com")]
    findings = _findings(resource, headers)
    assert any("ALLOW-FROM" in f.description for f in findings)


def test_xfo_invalid_value():
    resource = _resource()
    headers = [_header("X-Frame-Options", "ALLOWALL")]
    findings = _findings(resource, headers)
    assert any("invalid value" in f.description for f in findings)


def test_xcto_wrong_value():
    resource = _resource()
    headers = [_header("X-Content-Type-Options", "enabled")]
    findings = _findings(resource, headers)
    assert any("nosniff" in f.description for f in findings)


def test_referrer_unsafe_url():
    resource = _resource()
    headers = [_header("Referrer-Policy", "unsafe-url")]
    findings = _findings(resource, headers)
    assert any("leaks" in f.description for f in findings)


def test_referrer_invalid():
    resource = _resource()
    headers = [_header("Referrer-Policy", "whatever")]
    findings = _findings(resource, headers)
    assert any("invalid value" in f.description for f in findings)


def test_permissions_policy_empty():
    resource = _resource()
    headers = [_header("Permissions-Policy", "")]
    findings = _findings(resource, headers)
    assert any("empty" in f.description for f in findings)


def test_missing_headers_not_flagged():
    """This bit only validates values, not presence — missing_headers handles that."""
    resource = _resource()
    assert _findings(resource, []) == []
