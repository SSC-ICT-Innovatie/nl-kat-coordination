from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import HTTPHeader, HTTPResource

# Valid values for X-Frame-Options (RFC 7034)
VALID_XFO = {"deny", "sameorigin"}

# Valid values for Referrer-Policy (W3C)
VALID_REFERRER = {
    "no-referrer",
    "no-referrer-when-downgrade",
    "same-origin",
    "origin",
    "strict-origin",
    "origin-when-cross-origin",
    "strict-origin-when-cross-origin",
    "unsafe-url",
}

# Referrer-Policy values that leak origin information
WEAK_REFERRER = {"unsafe-url", "origin-when-cross-origin", "origin"}


def run(input_ooi: HTTPResource, additional_oois: list[HTTPHeader], config: dict[str, Any]) -> Iterator[OOI]:
    """Validate the values of security headers that are not already covered by
    check-hsts-header or check-csp-policy.

    Checks X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and
    Permissions-Policy for weak or invalid values. Presence is checked by
    missing-headers; this bit only runs on headers that are present.
    """
    headers = {h.key.lower(): h for h in additional_oois}
    issues: list[str] = []

    _check_xfo(headers, issues)
    _check_xcto(headers, issues)
    _check_referrer(headers, issues)
    _check_permissions_policy(headers, issues)

    if issues:
        description = "Security header value issues:\n" + "\n".join(f"  - {issue}" for issue in issues)
        ft = KATFindingType(id="KAT-HEADER-VALUE-ISSUES")
        yield ft
        yield Finding(finding_type=ft.reference, ooi=input_ooi.reference, description=description)


def _check_xfo(headers: dict[str, HTTPHeader], issues: list[str]) -> None:
    xfo = headers.get("x-frame-options")
    if xfo is None:
        return
    value = xfo.value.strip().lower()
    if value not in VALID_XFO:
        # ALLOW-FROM is deprecated and poorly supported
        if value.startswith("allow-from"):
            issues.append(
                "X-Frame-Options uses deprecated ALLOW-FROM directive; "
                "use Content-Security-Policy frame-ancestors instead"
            )
        else:
            issues.append(f"X-Frame-Options has invalid value '{xfo.value}'; expected DENY or SAMEORIGIN")


def _check_xcto(headers: dict[str, HTTPHeader], issues: list[str]) -> None:
    xcto = headers.get("x-content-type-options")
    if xcto is None:
        return
    if xcto.value.strip().lower() != "nosniff":
        issues.append(f"X-Content-Type-Options has invalid value '{xcto.value}'; expected 'nosniff'")


def _check_referrer(headers: dict[str, HTTPHeader], issues: list[str]) -> None:
    ref = headers.get("referrer-policy")
    if ref is None:
        return
    value = ref.value.strip().lower()
    if value not in VALID_REFERRER:
        issues.append(
            f"Referrer-Policy has invalid value '{ref.value}'; expected one of {', '.join(sorted(VALID_REFERRER))}"
        )
    elif value in WEAK_REFERRER:
        issues.append(
            f"Referrer-Policy value '{value}' leaks referrer information to third parties; "
            "consider 'no-referrer' or 'strict-origin-when-cross-origin'"
        )


def _check_permissions_policy(headers: dict[str, HTTPHeader], issues: list[str]) -> None:
    pp = headers.get("permissions-policy")
    if pp is None:
        return
    value = pp.value.strip()
    # An empty Permissions-Policy header is equivalent to not having one
    if not value:
        issues.append("Permissions-Policy header is empty; set explicit policies to restrict browser features")
