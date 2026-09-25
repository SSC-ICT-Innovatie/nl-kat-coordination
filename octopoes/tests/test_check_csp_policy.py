from bits.check_csp_policy.check_csp_policy import run

from octopoes.models import OOI, Reference
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import CSPDirective, CSPSource, HTTPHeader, HTTPResource


def _resource() -> HTTPResource:
    return HTTPResource(
        website=Reference.from_str("Website|internet|1.1.1.1|tcp|443|https|internet|example.com"),
        web_url=Reference.from_str("HostnameHTTPURL|https|internet|example.com|443|/"),
    )


def _policy_oois(csp_header: HTTPHeader, mapping: dict[str, list[str]]) -> list[OOI]:
    oois: list[OOI] = []
    for name, values in mapping.items():
        directive = CSPDirective(header=csp_header.reference, name=name)
        oois.append(directive)
        oois.extend(CSPSource(directive=directive.reference, value=value) for value in values)
    return oois


def _run(
    mapping: dict[str, list[str]], config: dict | None = None, content_type: str | None = "text/html"
) -> tuple[list[OOI], HTTPHeader]:
    resource = _resource()
    csp_header = HTTPHeader(resource=resource.reference, key="Content-Security-Policy", value="")
    additional: list[OOI] = [csp_header, *_policy_oois(csp_header, mapping)]
    if content_type is not None:
        additional.append(HTTPHeader(resource=resource.reference, key="Content-Type", value=content_type))
    return list(run(resource, additional, config or {})), csp_header


def _description(results: list[OOI]) -> str:
    return next(o.description for o in results if isinstance(o, Finding))


def test_non_xss_capable_resource_is_skipped():
    results, _ = _run({"script-src": ["*"]}, content_type="application/json")

    assert results == []


def test_missing_content_type_still_checks():
    results, _ = _run({"script-src": ["*"]}, content_type=None)

    assert any(isinstance(o, Finding) for o in results)


def test_no_csp_directives_yields_nothing():
    resource = _resource()
    content_type = HTTPHeader(resource=resource.reference, key="Content-Type", value="text/html")

    assert list(run(resource, [content_type], {})) == []


def test_complete_strict_policy_has_no_findings():
    results, _ = _run({"default-src": ["'self'"], "base-uri": ["'self'"], "frame-ancestors": ["'none'"]})

    assert not any(isinstance(o, Finding) for o in results)


def test_missing_required_directives_are_flagged():
    # default-src present -> the frame-src/script-src fallback groups are satisfied; base-uri and
    # frame-ancestors are missing.
    results, _ = _run({"default-src": ["'self'"]})

    description = _description(results)
    assert "base-uri has not been defined." in description
    assert "frame-ancestors has not been defined." in description
    assert "script-src has not been defined" not in description
    assert "frame-src has not been defined" not in description


def test_unsafe_wildcard_and_http_sources_are_flagged():
    mapping = {
        "default-src": ["'self'"],
        "base-uri": ["'self'"],
        "frame-ancestors": ["'none'"],
        "script-src": ["'unsafe-inline'", "*", "http://cdn.example.com"],
    }

    description = _description(_run(mapping)[0])
    assert "unsafe-inline" in description
    assert "wildcard" in description.lower()
    assert "Http should not be used" in description


def test_stray_asterisk_in_path_is_not_a_wildcard_finding():
    # A `*` outside the scheme/host part must not trigger the host-wildcard finding.
    mapping = {
        "default-src": ["'self'"],
        "base-uri": ["'self'"],
        "frame-ancestors": ["'none'"],
        "connect-src": ["https://example.com/collect?x=*"],
    }

    results, _ = _run(mapping)
    assert not any(isinstance(o, Finding) for o in results)


def test_private_ip_source_is_flagged():
    mapping = {
        "default-src": ["'self'"],
        "base-uri": ["'self'"],
        "frame-ancestors": ["'none'"],
        "connect-src": ["10.10.10.10"],
    }

    assert "Private, local, reserved" in _description(_run(mapping)[0])


def test_deprecated_directive_is_flagged():
    mapping = {
        "default-src": ["'self'"],
        "base-uri": ["'self'"],
        "frame-ancestors": ["'none'"],
        "report-uri": ["/csp-report"],
    }

    assert "Deprecated CSP directive found: report-uri" in _description(_run(mapping)[0])


def test_forbidden_keyword_message_names_the_actual_keyword():
    mapping = {
        "default-src": ["'self'"],
        "base-uri": ["'self'"],
        "frame-ancestors": ["'none'"],
        "script-src": ["'unsafe-eval'"],
    }

    description = _description(_run(mapping, config={"forbidden_keywords": "unsafe-eval"})[0])
    assert "Forbidden CSP source keyword(s) used: unsafe-eval." in description


def test_config_overrides_required_directives():
    # Only default-src required; base-uri/frame-ancestors are no longer flagged as missing.
    results, _ = _run({"default-src": ["'self'"]}, config={"required_directives": "default-src"})

    assert not any(isinstance(o, Finding) for o in results)


def test_finding_is_anchored_to_the_csp_header():
    results, csp_header = _run({"script-src": ["'self'"]})

    finding = next(o for o in results if isinstance(o, Finding))
    assert finding.ooi == csp_header.reference
    assert KATFindingType(id="KAT-CSP-VULNERABILITIES") in results


STRICT_WITH_HOSTS = {
    "default-src": ["'self'"],
    "base-uri": ["'self'"],
    "frame-ancestors": ["'none'"],
    "style-src": ["https://cdn.example.com", "https://fonts.trusted.example/css/"],
}


def test_no_allowlist_config_accepts_any_host():
    results, _ = _run(STRICT_WITH_HOSTS)

    assert not any(isinstance(o, Finding) for o in results)


def test_allowlist_reports_hosts_outside_it():
    description = _description(_run(STRICT_WITH_HOSTS, config={"allowed_hosts": "cdn.example.com"})[0])

    assert "CSP source host(s) not in the configured allowlist: fonts.trusted.example." in description


def test_allowlist_accepts_exact_and_wildcard_entries():
    results, _ = _run(STRICT_WITH_HOSTS, config={"allowed_hosts": "cdn.example.com,*.trusted.example"})

    assert not any(isinstance(o, Finding) for o in results)


def test_allowlist_ignores_keywords_schemes_and_nonces():
    mapping = {
        "default-src": ["'self'"],
        "base-uri": ["'self'"],
        "frame-ancestors": ["'none'"],
        "img-src": ["data:"],
        "script-src": ["'nonce-r4nd0m'", "'sha256-abc123'"],
    }

    results, _ = _run(mapping, config={"allowed_hosts": "cdn.example.com"})

    assert not any(isinstance(o, Finding) for o in results)


def test_allowlist_strips_scheme_port_and_path_and_ignores_case():
    mapping = {
        "default-src": ["'self'"],
        "base-uri": ["'self'"],
        "frame-ancestors": ["'none'"],
        "style-src": ["https://CDN.Example.com:8443/styles/"],
    }

    results, _ = _run(mapping, config={"allowed_hosts": "cdn.example.com"})

    assert not any(isinstance(o, Finding) for o in results)


def test_allowlist_leaves_wildcard_sources_to_the_wildcard_check():
    mapping = {
        "default-src": ["'self'"],
        "base-uri": ["'self'"],
        "frame-ancestors": ["'none'"],
        "style-src": ["*.evil.example"],
    }

    description = _description(_run(mapping, config={"allowed_hosts": "cdn.example.com"})[0])

    assert "wildcard" in description
    assert "allowlist" not in description
