from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import HTTPHeader, HTTPResource

DEPRECATED_HEADER = {
    "x-forwarded-host",
    "x-forwarded-proto",
    "x-dns-prefetch-control",
    "x-forwarded-for",
    "x-robots-tag",
    "pragma",
    "warning",
}

XSS_CAPABLE_TYPES = ["text/html", "application/xhtml+xml", "application/xml", "text/xml", "image/svg+xml"]


def is_xss_capable(content_type: str) -> bool:
    """Determine if the content type indicates XSS capability."""
    main_type = content_type.split(";")[0].strip().lower()
    return main_type in XSS_CAPABLE_TYPES


def run(resource: HTTPResource, additional_oois: list[HTTPHeader], config: dict[str, Any]) -> Iterator[OOI]:
    if not additional_oois:
        return

    header_keys = [header.key.lower() for header in additional_oois]
    headers = {header.key.lower(): header.value for header in additional_oois}

    if "location" in header_keys:
        return

    if "strict-transport-security" not in header_keys and resource.reference.tokenized.web_url.scheme != "http":
        ft = KATFindingType(id="KAT-NO-HSTS")
        yield ft
        finding = Finding(
            finding_type=ft.reference,
            ooi=resource.reference,
            description="Header strict-transport-security is missing or not configured correctly.",
        )
        yield finding

    if "content-security-policy" not in header_keys and is_xss_capable(headers.get("content-type", "")):
        ft = KATFindingType(id="KAT-NO-CSP")
        finding = Finding(
            finding_type=ft.reference,
            ooi=resource.reference,
            description="Header content-security-policy is missing or not configured correctly.",
        )
        yield ft
        yield finding

    if "x-frame-options" not in header_keys:
        ft = KATFindingType(id="KAT-NO-X-FRAME-OPTIONS")
        finding = Finding(
            finding_type=ft.reference,
            ooi=resource.reference,
            description="Header x-frame-options is missing or not configured correctly.",
        )
        yield ft
        yield finding

    if "permissions-policy" not in header_keys:
        ft = KATFindingType(id="KAT-NO-PERMISSIONS-POLICY")
        finding = Finding(
            finding_type=ft.reference,
            ooi=resource.reference,
            description="Header permissions-policy is missing or not configured correctly.",
        )
        yield ft
        yield finding

    if "referrer-policy" not in header_keys:
        ft = KATFindingType(id="KAT-NO-REFERRER-POLICY")
        finding = Finding(
            finding_type=ft.reference,
            ooi=resource.reference,
            description="Header referrer-policy is missing or not configured correctly.",
        )
        yield ft
        yield finding

    if "x-content-type-options" not in header_keys:
        ft = KATFindingType(id="KAT-NO-X-CONTENT-TYPE-OPTIONS")
        finding = Finding(
            finding_type=ft.reference,
            ooi=resource.reference,
            description="Header x-content-type-options is missing or not configured correctly.",
        )
        yield ft
        yield finding

    deprecated_headers = set(header_keys) & DEPRECATED_HEADER
    if deprecated_headers:
        ft = KATFindingType(id="KAT-NONSTANDARD-HEADERS")
        finding = Finding(
            finding_type=ft.reference,
            ooi=resource.reference,
            description=f"Nonstandard headers are used. Avoid using the following headers: "
            f"{' '.join(deprecated_headers)}",
        )
        yield ft
        yield finding
