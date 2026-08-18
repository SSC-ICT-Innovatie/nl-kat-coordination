"""Normalize raw HTTP response headers into HTTPHeader and Cookie OOIs.

Volatile values (session tokens, trace ids, timestamps) are nulled per the
curated set in volatile_headers.json so that repeated observations of the same
endpoint produce an identical OOI set instead of a fresh mutation chain per
scan. Names, attributes and the existence of a header are always preserved —
only values are redacted. See
https://github.com/SSC-ICT-Innovatie/nl-kat-coordination/issues/213.
"""

import contextlib
import fnmatch
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network
from octopoes.models.ooi.web import Cookie, HTTPHeader

_VOLATILE = json.loads((Path(__file__).parent / "volatile_headers.json").read_text())
VOLATILE_HEADERS = frozenset(_VOLATILE["headers"])
VOLATILE_COOKIE_PATTERNS = tuple(_VOLATILE["cookies"])

REDACTED = "<redacted>"

# Legacy raws hold headers as a dict, where requests joined repeated Set-Cookie
# headers with ", ". Split only where the next segment looks like the start of a
# cookie (name=), which an Expires date continuation ("28 Feb ...") never does.
_LEGACY_COOKIE_SPLIT = re.compile(r",(?=\s*[^\s;,=]+=)")

# RFC 6265 5.1.1 wants a very lenient date parser; browsers accept all of these.
_EXPIRES_FORMATS = (
    "%a, %d %b %Y %H:%M:%S %Z",
    "%a, %d-%b-%Y %H:%M:%S %Z",
    "%a, %d-%b-%y %H:%M:%S %Z",
    "%a, %d %b %y %H:%M:%S %Z",
    "%d %b %Y %H:%M:%S %Z",
)

_SAME_SITE_VALUES = {"strict": "Strict", "lax": "Lax", "none": "None"}

_DAY = 86400


@dataclass
class ParsedCookie:
    name: str
    value: str
    domain: str | None = None
    path: str | None = None
    max_age: int | None = None
    expires: datetime | None = None
    has_expires_attribute: bool = False
    secure: bool = False
    http_only: bool = False
    same_site: str | None = None
    unknown_attributes: list[str] = field(default_factory=list)


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    resource = Reference.from_str(input_ooi["primary_key"])
    tokenized = resource.tokenized
    request_host = tokenized.website.hostname.name.lower()
    network = Network(name=tokenized.website.hostname.network.name)
    request_path = str(tokenized.web_url.path)

    parsed = json.loads(raw)
    is_legacy = isinstance(parsed, dict)
    pairs = list(parsed.items()) if is_legacy else [(item[0], item[1]) for item in parsed]

    set_cookie_values: list[str] = []
    # HTTPHeader identity is (resource, key), so repeated headers (Via, Link, …)
    # must fold into one value, joined with ", " like the legacy dict shape did.
    merged_headers: dict[str, tuple[str, list[str]]] = {}

    for key, value in pairs:
        lower_key = key.lower()

        if lower_key == "set-cookie":
            if is_legacy:
                set_cookie_values.extend(part.strip() for part in _LEGACY_COOKIE_SPLIT.split(value))
            else:
                set_cookie_values.append(value)
            continue

        merged_headers.setdefault(lower_key, (key, []))[1].append(value)

    # The Date header is itself volatile (nulled below), but it is the deterministic
    # reference point for converting absolute Expires dates into relative lifetimes.
    response_date = parse_expires(merged_headers["date"][1][0]) if "date" in merged_headers else None

    for lower_key, (key, values) in merged_headers.items():
        value = REDACTED if lower_key in VOLATILE_HEADERS else ", ".join(values)

        yield HTTPHeader(resource=resource, key=key, value=value)

    if not set_cookie_values:
        return

    canonical_values = []
    for set_cookie in set_cookie_values:
        cookie = parse_set_cookie(set_cookie)
        if cookie is None:
            continue

        canonical_values.append(serialize_canonical(cookie))
        yield from cookie_oois(cookie, request_host, request_path, network, response_date)

    if canonical_values:
        # HTTPHeader identity is (resource, key), so all Set-Cookie headers fold
        # into one OOI. Joining the canonical forms keeps that value stable.
        yield HTTPHeader(resource=resource, key="Set-Cookie", value=", ".join(canonical_values))


def parse_set_cookie(set_cookie: str) -> ParsedCookie | None:
    """Parse one set-cookie-string per RFC 6265 5.2 (lenient, browser-like).

    Broken attributes are ignored rather than rejected: browsers keep the
    cookie, so a parse failure is not a finding.
    """
    first, *attribute_parts = set_cookie.split(";")

    if "=" not in first:
        # Nameless cookie: RFC 6265 5.2 ignores the set-cookie-string entirely.
        return None

    name, _, value = first.partition("=")
    name = name.strip()
    if not name:
        return None

    cookie = ParsedCookie(name=name, value=value.strip())

    for part in attribute_parts:
        attribute, _, attribute_value = part.partition("=")
        attribute = attribute.strip().lower()
        attribute_value = attribute_value.strip()

        if attribute == "domain" and attribute_value:
            cookie.domain = attribute_value.lstrip(".").lower()
        elif attribute == "path" and attribute_value.startswith("/"):
            cookie.path = attribute_value
        elif attribute == "max-age":
            with contextlib.suppress(ValueError):
                cookie.max_age = int(attribute_value)
        elif attribute == "expires":
            cookie.has_expires_attribute = True
            cookie.expires = parse_expires(attribute_value)
        elif attribute == "secure":
            cookie.secure = True
        elif attribute == "httponly":
            cookie.http_only = True
        elif attribute == "samesite":
            cookie.same_site = _SAME_SITE_VALUES.get(attribute_value.lower())
        elif attribute:
            cookie.unknown_attributes.append(part.strip())

    return cookie


def parse_expires(value: str) -> datetime | None:
    value = value.strip()
    for fmt in _EXPIRES_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def serialize_canonical(cookie: ParsedCookie) -> str:
    """Reserialize with a redacted-if-volatile value and in a fixed attribute order.

    An empty value would be ambiguous with the cookie-deletion idiom
    ("name=; Expires=<past>"), which is a meaningful observation in itself, so
    volatile values become an explicit sentinel instead. The absolute Expires
    date (which rolls on every response) is reduced to the same sentinel; the
    relative lifetime lives on the Cookie OOI.
    """
    value = REDACTED if is_volatile_cookie(cookie.name) else cookie.value

    parts = [f"{cookie.name}={value}"]
    if cookie.domain:
        parts.append(f"Domain={cookie.domain}")
    if cookie.path:
        parts.append(f"Path={cookie.path}")
    if cookie.max_age is not None:
        parts.append(f"Max-Age={cookie.max_age}")
    elif cookie.has_expires_attribute:
        parts.append(f"Expires={REDACTED}")
    if cookie.secure:
        parts.append("Secure")
    if cookie.http_only:
        parts.append("HttpOnly")
    if cookie.same_site:
        parts.append(f"SameSite={cookie.same_site}")
    parts.extend(sorted(cookie.unknown_attributes))

    return "; ".join(parts)


def is_volatile_cookie(name: str) -> bool:
    lower_name = name.lower()

    return any(fnmatch.fnmatchcase(lower_name, pattern) for pattern in VOLATILE_COOKIE_PATTERNS)


def cookie_oois(
    cookie: ParsedCookie, request_host: str, request_path: str, network: Network, response_date: datetime | None
) -> Iterable[NormalizerOutput]:
    if "|" in cookie.name or "|" in (cookie.path or ""):
        # A pipe would corrupt the natural key (reference separator); a cookie
        # name/path containing one is hostile or garbage either way.
        return

    # https://datatracker.ietf.org/doc/html/rfc6265#section-5.3 p6: a Domain
    # that does not domain-match the request host is ignored by user agents.
    # Honoring it here would let a scanned server inject arbitrary Hostname
    # OOIs into the graph.
    host_only = True
    domain = request_host
    if cookie.domain and domain_matches(request_host, cookie.domain):
        host_only = False
        domain = cookie.domain

    persistent, lifetime = lifetime_bucket(cookie, response_date)

    hostname = Hostname(network=network.reference, name=domain)
    yield hostname
    yield Cookie(
        name=cookie.name,
        domain=hostname.reference,
        path=cookie.path or default_path(request_path),
        secure_only=cookie.secure,
        http_only=cookie.http_only,
        same_site=cookie.same_site,
        host_only=host_only,
        persistent=persistent,
        lifetime=lifetime,
        value_size=value_size_bucket(cookie.value),
    )


def domain_matches(request_host: str, domain: str) -> bool:
    # https://datatracker.ietf.org/doc/html/rfc6265#section-5.1.3
    return request_host == domain or request_host.endswith("." + domain)


def default_path(request_path: str) -> str:
    # https://datatracker.ietf.org/doc/html/rfc6265#section-5.1.4
    if not request_path.startswith("/"):
        return "/"

    last_slash = request_path.rfind("/")

    return "/" if last_slash == 0 else request_path[:last_slash]


def lifetime_bucket(cookie: ParsedCookie, response_date: datetime | None) -> tuple[bool, str | None]:
    """Bucket the relative lifetime; Max-Age wins over Expires (RFC 6265 5.3 p3).

    The bucket replaces the absolute Expires date so that rolling expiries do
    not change the OOI on every observation. The response's own Date header is
    the reference point, keeping the output deterministic on re-normalization.
    """
    if cookie.max_age is not None:
        return True, _bucket(cookie.max_age)

    if cookie.expires is not None:
        if response_date is None:
            return True, None

        return True, _bucket((cookie.expires - response_date).total_seconds())

    return False, "session"


def _bucket(seconds: float) -> str:
    if seconds <= _DAY:
        return "<1d"
    if seconds <= 30 * _DAY:
        return "<30d"
    if seconds <= 400 * _DAY:
        return ">30d"

    return ">400d"


def value_size_bucket(value: str) -> str:
    size = len(value.encode())
    if size < 1024:
        return "<1KB"
    if size < 4096:
        return "1-4KB"

    return ">4KB"
