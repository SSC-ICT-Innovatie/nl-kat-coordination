from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import Cookie


def run(cookie: Cookie, additional_oois: list, config: dict[str, Any]) -> Iterator[OOI]:
    """Assess the security attributes of a parsed Cookie.

    The attributes are already parsed onto the Cookie OOI by the headers
    normalizer (RFC 6265 5.2), so this bit only inspects fields — no string
    parsing. The issue list is emitted in a fixed order so repeated runs
    produce a byte-identical Finding.
    """
    issues = []

    if not cookie.secure_only:
        issues.append("the Secure attribute is not set, so the cookie may be sent over an unencrypted connection")

    if not cookie.http_only:
        issues.append("the HttpOnly attribute is not set, so client-side scripts can read the cookie (XSS risk)")

    if cookie.same_site is None:
        issues.append("no valid SameSite attribute is set, so the cookie is sent with cross-site requests (CSRF risk)")
    elif cookie.same_site == "None" and not cookie.secure_only:
        issues.append("SameSite=None is set without the Secure attribute; modern browsers reject such cookies")

    # https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-rfc6265bis-19#section-4.1.3
    if cookie.name.startswith("__Host-") and not (cookie.secure_only and cookie.host_only and cookie.path == "/"):
        issues.append("the __Host- name prefix requires the Secure attribute, no Domain attribute and Path=/")
    elif cookie.name.startswith("__Secure-") and not cookie.secure_only:
        issues.append("the __Secure- name prefix requires the Secure attribute")

    if not issues:
        return

    finding_type = KATFindingType(id="KAT-INSECURE-COOKIE")
    yield finding_type
    yield Finding(
        finding_type=finding_type.reference,
        ooi=cookie.reference,
        description="Insecure cookie configuration: " + "; ".join(issues) + ".",
    )
