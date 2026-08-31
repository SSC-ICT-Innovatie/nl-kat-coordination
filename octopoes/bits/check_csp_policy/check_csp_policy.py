import ipaddress
import re
from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import CSPDirective, CSPSource, HTTPHeader, HTTPResource

NON_DECIMAL_FILTER = re.compile(r"[^\d.]+")  # extracts an IP-like substring from a source; not used for matching

XSS_CAPABLE_TYPES = ["text/html", "application/xhtml+xml", "application/xml", "text/xml", "image/svg+xml"]

DEFAULT_REQUIRED_DIRECTIVES = ["base-uri", "frame-ancestors", "default-src"]
DEFAULT_DEPRECATED_DIRECTIVES = ["block-all-mixed-content", "prefetch-src", "report-uri"]
DEFAULT_FORBIDDEN_KEYWORDS = ["unsafe-inline", "unsafe-eval", "unsafe-hashes"]


def _keyword(source: str) -> str:
    """A CSP keyword source without its surrounding quotes, lowercased (`'Self'` -> `self`)."""
    return source.strip("'").lower()


def _as_list(config: dict[str, Any], key: str, default: list[str]) -> list[str]:
    """Read a list-valued config key, tolerating both a JSON array and a comma-separated string (the
    shape a Question form stores). A missing key falls back to the default."""
    value = config.get(key)
    if value is None:
        return default
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return list(value)


def _is_xss_capable(content_type: str) -> bool:
    return content_type.split(";")[0].strip().lower() in XSS_CAPABLE_TYPES


def _is_host_wildcard(source: str) -> bool:
    """True for a wildcard in the scheme/host part of a source (`*`, `*.example.com`, `https://*`), but
    not for a stray asterisk elsewhere in a value."""
    return source == "*" or source.startswith("*.") or "://*" in source


def _ip_is_global(source: str) -> bool:
    """False when the source contains a non-global (private/loopback/reserved/…) IP; True otherwise."""
    ip_str = NON_DECIMAL_FILTER.sub("", source)
    if not ip_str:
        return True
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved)


def run(input_ooi: HTTPResource, additional_oois: list, config: dict[str, Any]) -> Iterator[OOI]:
    """Check a parsed Content-Security-Policy for security problems, driven by an optional Config.

    Consumes an HTTPResource plus its headers and the structured CSPDirective/CSPSource OOIs produced by
    the parse-csp bit, so every check is a plain set/string operation — no backtracking regex and no
    whole-string substring matching, unlike the retired check_csp_header bit. Like that bit it skips
    non-XSS-capable resources. The required/deprecated directive lists and forbidden keywords are
    overridable by a Config OOI on the Network; the defaults reproduce the previous checks.
    """
    header_by_key = {ooi.key.lower(): ooi for ooi in additional_oois if isinstance(ooi, HTTPHeader)}

    content_type = header_by_key.get("content-type")
    if content_type is not None and not _is_xss_capable(content_type.value):
        return

    csp_header = header_by_key.get("content-security-policy")
    if csp_header is None:
        return

    directives = [
        ooi for ooi in additional_oois if isinstance(ooi, CSPDirective) and ooi.header == csp_header.reference
    ]
    if not directives:
        return
    directive_references = {directive.reference for directive in directives}
    sources = [ooi for ooi in additional_oois if isinstance(ooi, CSPSource) and ooi.directive in directive_references]

    name_by_reference = {directive.reference: directive.name for directive in directives}
    policy: dict[str, list[str]] = {directive.name: [] for directive in directives}
    for source in sources:
        name = name_by_reference.get(source.directive)
        if name is not None:
            policy.setdefault(name, []).append(source.value)

    names = set(policy)
    all_sources = [value for values in policy.values() for value in values]

    required = _as_list(config, "required_directives", DEFAULT_REQUIRED_DIRECTIVES)
    deprecated = _as_list(config, "deprecated_directives", DEFAULT_DEPRECATED_DIRECTIVES)
    forbidden_keywords = {
        _keyword(keyword) for keyword in _as_list(config, "forbidden_keywords", DEFAULT_FORBIDDEN_KEYWORDS)
    }

    findings: list[str] = []

    # Source-level problems (evaluated per source, so no substring false positives and no regex).
    if any(source.startswith("http://") for source in all_sources):
        findings.append("Http should not be used in the CSP settings of an HTTP Header.")
    if any(_is_host_wildcard(source) for source in all_sources):
        findings.append("The wildcard * for the scheme and host part of any URL should never be used in CSP settings.")
    if any(source in ("http:", "https:") for source in all_sources):
        findings.append("A blanket protocol source should not be used in the value of any type in the CSP settings.")
    forbidden_used = sorted({_keyword(source) for source in all_sources if _keyword(source) in forbidden_keywords})
    if forbidden_used:
        findings.append(f"Forbidden CSP source keyword(s) used: {', '.join(forbidden_used)}.")
    if any(not _ip_is_global(source) for source in all_sources):
        findings.append("Private, local, reserved, multicast, loopback ips should not be allowed in the CSP settings.")

    # Required directives, plus the two fallback groups.
    for directive in required:
        if directive not in names:
            findings.append(f"{directive} has not been defined.")
    if not names & {"frame-src", "default-src", "child-src"}:
        findings.append("frame-src has not been defined or does not have a fallback.")
    if not names & {"script-src", "default-src"}:
        findings.append("script-src has not been defined or does not have a fallback.")

    # Deprecated directives.
    for directive in deprecated:
        if directive in names:
            findings.append(f"Deprecated CSP directive found: {directive}")

    # Per-directive semantic rules.
    if "default-src" in names and not any(_keyword(source) in ("none", "self") for source in policy["default-src"]):
        findings.append("default-src should contain 'none' or 'self'.")
    for directive in ("default-src", "object-src", "script-src"):
        if any(_keyword(source) == "data:" for source in policy.get(directive, [])):
            findings.append(
                "'data:' should not be used in the value of default-src, object-src and script-src in the CSP settings."
            )
    if any(_keyword(source) == "self" for source in policy.get("script-src", [])):
        findings.append("'self' for script-src can be problematic if you host JSONP, Angular or user uploaded files.")
    for name, values in policy.items():
        if name.endswith("-uri") and any(
            _keyword(value) in ("unsafe-eval", "unsafe-hashes", "unsafe-inline", "strict-dynamic") for value in values
        ):
            findings.append(f"{name} has illogical values.")

    if findings:
        description = "List of CSP findings:\n" + "\n".join(
            f" {index + 1}. {finding}" for index, finding in enumerate(findings)
        )
        finding_type = KATFindingType(id="KAT-CSP-VULNERABILITIES")
        yield finding_type
        yield Finding(finding_type=finding_type.reference, ooi=csp_header.reference, description=description)
