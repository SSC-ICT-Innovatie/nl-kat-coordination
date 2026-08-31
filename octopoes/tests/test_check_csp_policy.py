from bits.check_csp_policy.check_csp_policy import run

from octopoes.models import OOI, Reference
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import CSPDirective, CSPSource, HTTPHeader

RESOURCE = "HTTPResource|internet|1.1.1.1|tcp|443|https|internet|example.com|https|internet|example.com|443|/"


def _header(key: str = "Content-Security-Policy") -> HTTPHeader:
    return HTTPHeader(resource=Reference.from_str(RESOURCE), key=key, value="")


def _policy(header: HTTPHeader, mapping: dict[str, list[str]]) -> list[OOI]:
    oois: list[OOI] = []
    for name, values in mapping.items():
        directive = CSPDirective(header=header.reference, name=name)
        oois.append(directive)
        oois.extend(CSPSource(directive=directive.reference, value=value) for value in values)
    return oois


def _description(results: list[OOI]) -> str:
    return next(o.description for o in results if isinstance(o, Finding))


def test_non_csp_header_is_ignored():
    header = _header(key="Content-Type")

    assert list(run(header, _policy(header, {"default-src": ["'self'"]}), {})) == []


def test_no_directives_yields_nothing():
    assert list(run(_header(), [], {})) == []


def test_complete_strict_policy_has_no_findings():
    header = _header()
    mapping = {"default-src": ["'self'"], "base-uri": ["'self'"], "frame-ancestors": ["'none'"]}

    results = list(run(header, _policy(header, mapping), {}))

    assert not any(isinstance(o, Finding) for o in results)


def test_missing_required_directives_are_flagged():
    header = _header()

    # default-src is present, so the frame-src/script-src fallback groups are satisfied; base-uri and
    # frame-ancestors are missing.
    description = _description(list(run(header, _policy(header, {"default-src": ["'self'"]}), {})))

    assert "base-uri has not been defined." in description
    assert "frame-ancestors has not been defined." in description
    assert "script-src has not been defined" not in description
    assert "frame-src has not been defined" not in description


def test_unsafe_wildcard_and_http_sources_are_flagged():
    header = _header()
    mapping = {
        "default-src": ["'self'"],
        "base-uri": ["'self'"],
        "frame-ancestors": ["'none'"],
        "script-src": ["'unsafe-inline'", "*", "http://cdn.example.com"],
    }

    description = _description(list(run(header, _policy(header, mapping), {})))

    assert "unsafe-inline" in description
    assert "wildcard" in description.lower()
    assert "Http should not be used" in description


def test_private_ip_source_is_flagged():
    header = _header()
    mapping = {
        "default-src": ["'self'"],
        "base-uri": ["'self'"],
        "frame-ancestors": ["'none'"],
        "connect-src": ["10.10.10.10"],
    }

    assert "Private, local, reserved" in _description(list(run(header, _policy(header, mapping), {})))


def test_deprecated_directive_is_flagged():
    header = _header()
    mapping = {
        "default-src": ["'self'"],
        "base-uri": ["'self'"],
        "frame-ancestors": ["'none'"],
        "report-uri": ["/csp-report"],
    }

    assert "Deprecated CSP directive found: report-uri" in _description(list(run(header, _policy(header, mapping), {})))


def test_config_overrides_required_directives():
    header = _header()

    # Only default-src required; base-uri/frame-ancestors are no longer flagged as missing.
    results = list(run(header, _policy(header, {"default-src": ["'self'"]}), {"required_directives": "default-src"}))

    assert not any(isinstance(o, Finding) for o in results)


def test_finding_is_anchored_to_the_header():
    header = _header()

    results = list(run(header, _policy(header, {"script-src": ["'self'"]}), {}))

    finding = next(o for o in results if isinstance(o, Finding))
    assert finding.ooi == header.reference
    assert KATFindingType(id="KAT-CSP-VULNERABILITIES") in results
