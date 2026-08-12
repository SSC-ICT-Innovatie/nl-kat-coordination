import ipaddress
import re
from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI, Reference
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import HTTPResource
from octopoes.models.types import HTTPHeader

NON_DECIMAL_FILTER = re.compile(r"[^\d.]+")

XSS_CAPABLE_TYPES = ["text/html", "application/xhtml+xml", "application/xml", "text/xml", "image/svg+xml"]

DEPRECATED_DIRECTIVES = ["block-all-mixed-content", "prefetch-src"]


def is_xss_capable(content_type: str) -> bool:
    """Determine if the content type indicates XSS capability."""
    main_type = content_type.split(";")[0].strip().lower()
    return main_type in XSS_CAPABLE_TYPES


def run(resource: HTTPResource, additional_oois: list[HTTPHeader], config: dict[str, Any]) -> Iterator[OOI]:
    if not additional_oois:
        return

    headers = {header.key.lower(): header.value for header in additional_oois}

    content_type = headers.get("content-type", "")
    # if no content type is present, we can't determine if the resource is XSS capable, so assume it is
    if content_type and not is_xss_capable(content_type):
        return

    csp_header = headers.get("content-security-policy", "")

    if not csp_header:
        return

    findings: list[str] = []

    if "http://" in csp_header:
        findings.append("Http should not be used in the CSP settings of an HTTP Header.")

    # checks for a wildcard in domains in the header
    # 1: one or more non-whitespace
    # 2: wildcard
    # 3: second-level domain
    # 4: end with either a space, a ';', a :port or the end of the string
    #              {1}{ 2}{  3  }{         4       }
    if re.search(r"\S+\*\.\S{2,3}([\s]+|$|;|:\d+)", csp_header):
        findings.append("The wildcard * for the scheme and host part of any URL should never be used in CSP settings.")

    if "unsafe-inline" in csp_header or "unsafe-eval" in csp_header or "unsafe-hashes" in csp_header:
        findings.append(
            "unsafe-inline, unsafe-eval and unsafe-hashes should not be used in the CSP settings of an HTTP Header."
        )

    if "frame-src" not in csp_header and "default-src" not in csp_header and "child-src" not in csp_header:
        findings.append("frame-src has not been defined or does not have a fallback.")

    if "script-src" not in csp_header and "default-src" not in csp_header:
        findings.append("script-src has not been defined or does not have a fallback.")

    if "base-uri" not in csp_header:
        findings.append("base-uri has not been defined, default-src does not apply.")

    if "frame-ancestors" not in csp_header:
        findings.append("frame-ancestors has not been defined.")

    if "default-src" not in csp_header:
        findings.append("default-src has not been defined.")

    for deprecated_directive in DEPRECATED_DIRECTIVES:
        if deprecated_directive in csp_header:
            findings.append(f"Deprecated CSP directive found: {deprecated_directive}")

    if "report-uri" in csp_header:
        findings.append("""Deprecated CSP directive found. report-uri is superseded by report-to:
        https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy/report-uri""")

    policies = [policy.strip().split(" ") for policy in csp_header.split(";")]
    for policy in policies:
        if len(policy) < 2:
            findings.append("CSP setting has no value.")
            continue

        if policy[0] in ["frame-src", "frame-ancestors"] and not _source_valid(policy[1:]):
            findings.append(f"{policy[0]} has not been correctly defined.")

        if policy[0] == "default-src" and (
            ("'none'" not in policy and "'self'" not in policy) or not _source_valid(policy[2:])
        ):
            findings.append(f"{policy[0]} has not been correctly defined.")

        if (policy[0] == "default-src" or policy[0] == "object-src" or policy[0] == "script-src") and "data:" in policy:
            findings.append(
                "'data:' should not be used in the value of default-src, object-src and script-src in the CSP settings."
            )

        if policy[0] == "script-src" and "'self'" in policy:
            findings.append(
                "'self' for `script-src` can be problematic if you host JSONP, Angular or user uploaded files."
            )

        if policy[0].endswith("-uri") and (
            "unsafe-eval" in policy[2:]
            or "unsafe-hashes" in policy[2:]
            or "unsafe-inline" in policy[2:]
            or "strict-dynamic" in policy[2:]
        ):
            findings.append(f"{policy[0]} has illogical values.")

        if policy[1].strip() == "*":
            findings.append("A wildcard source should not be used in the value of any type in the CSP settings.")
        if policy[1].strip() in ("http:", "https:"):
            findings.append(
                "a blanket protocol source should not be used in the value of any type in the CSP settings."
            )
        for source in policy[1:]:
            if not _ip_valid(source):
                findings.append(
                    "Private, local, reserved, multicast, loopback ips should not be allowed in the CSP settings."
                )
    if findings:
        description: str = "List of CSP findings:"
        for index, finding in enumerate(findings):
            description += f"\n {index + 1}. {finding}"

        yield from _create_kat_finding(resource.reference, kat_id="KAT-CSP-VULNERABILITIES", description=description)


def _ip_valid(source: str) -> bool:
    "Check if there are IP's in this source, return False if the address found was to be non global. Ignores non ips"
    ip_str = NON_DECIMAL_FILTER.sub("", source)
    if ip_str:
        try:
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                return False
        except ValueError:
            pass
    return True


def _create_kat_finding(header: Reference, kat_id: str, description: str) -> Iterator[OOI]:
    finding_type = KATFindingType(id=kat_id)
    yield finding_type
    yield Finding(finding_type=finding_type.reference, ooi=header, description=description)


def _source_valid(policy: list[str]) -> bool:
    for value in policy:
        if not (
            re.search(r"\S+\.\S{2,3}([\s]+|$|;|:\d+)", value)
            or value in ["'none'", "'self'", "data:", "unsafe-inline", "unsafe-eval", "unsafe-hashes", "report-sample"]
        ):
            return False

    return True
