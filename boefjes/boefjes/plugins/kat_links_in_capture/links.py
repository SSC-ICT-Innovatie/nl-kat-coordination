"""Find hostnames behind the links on a captured page.

`webpage-capture` produces a Playwright browser HAR, so the document in it is the one
the browser rendered. Anchors injected by JavaScript are present there, where the
static `webpage-analysis` HTML has none of them.

Only hostnames are minted, never URLs. The question this answers is "which hosts does
this page point at", and emitting a URL per link would add an object per path without
finding a single extra host.

Each hostname carries its `registered_domain`, and that is what decides whether it is
ever scanned: a subdomain of an apex the organisation has cleared inherits that
clearance, and anything else stays at L0, where no boefje consumes a Hostname and no
finding-producing bit runs.

A page is attacker-influenced input, so nothing here may raise: one malformed href
would abort the task and cost every hostname on the page, not just that one link.
"""

import json
import logging
from collections.abc import Iterable
from urllib.parse import urljoin, urlparse

import tldextract
from bs4 import BeautifulSoup
from pydantic import ValidationError

from boefjes.normalizer_models import NormalizerOutput
from boefjes.plugins.kat_wappalyzer.har_zip import har_from_playwright_zip
from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network

logger = logging.getLogger(__name__)

# tldextract consults only the ICANN section of the public suffix list by default, which
# collapses every tenant of a shared platform onto the platform itself: `a.github.io` and
# `b.github.io` would both come out as `github.io`. Including the private section keeps
# them apart, so that "same registrable domain" keeps meaning "same owner" -- which is
# the whole basis for inheriting clearance below.
_EXTRACT = tldextract.TLDExtract(include_psl_private_domains=True)


def registrable_domain(hostname: str) -> str:
    return _EXTRACT(hostname).top_domain_under_public_suffix


def normalised(hostname: str) -> str | None:
    """A hostname in the same form the Hostname OOI stores, or None if it is not one.

    `Hostname` punycodes its name, so a primary key holds `xn--mller-kva.de` where an
    href holds `müller.de`. Comparing those two without normalising first makes the
    in-zone test fail for every internationalised domain, and hands the organisation's
    own domain to the third-party normalizer instead.
    """
    hostname = hostname.rstrip(".").lower()

    if not hostname:
        return None

    try:
        return hostname.encode("idna").decode()
    except UnicodeError:
        return None


def _document_entry(har: dict) -> dict | None:
    """The HAR entry holding the page itself.

    Not simply the first HTML entry: a redirect carries its own HTML body often enough
    (the server's default "Moved Permanently" page), and parsing that instead of the
    page finds no links at all.
    """
    for entry in har.get("log", {}).get("entries", []):
        response = entry.get("response", {})

        if 300 <= (response.get("status") or 0) < 400:
            continue

        content = response.get("content", {})

        if "html" in (content.get("mimeType") or "") and content.get("text"):
            return entry

    return None


def hostnames_from_capture(raw: bytes) -> set[str]:
    """Hostnames behind the `<a href>` links in the captured document."""
    entry = _document_entry(json.loads(har_from_playwright_zip(raw)))

    if entry is None:
        return set()

    soup = BeautifulSoup(entry["response"]["content"]["text"], "html.parser")
    base = entry.get("request", {}).get("url", "")

    # A <base href> changes what every relative link on the page resolves to.
    if (base_tag := soup.find("base", href=True)) is not None:
        base = urljoin(base, base_tag["href"].strip())

    hostnames = set()

    for anchor in soup.find_all("a", href=True):
        # Relative hrefs are the common case, and mailto:, tel: and javascript: links
        # resolve to a scheme we drop below rather than to a host.
        try:
            parsed = urlparse(urljoin(base, anchor["href"].strip()))
            host = parsed.hostname
        except ValueError:
            # A malformed href ("https://host]/") is one bad link, not a bad page.
            continue

        if parsed.scheme in ("http", "https") and host and (host := normalised(host)):
            hostnames.add(host)

    return hostnames


def hostname_oois(input_ooi: dict, raw: bytes, external: bool) -> Iterable[NormalizerOutput]:
    """Yield the linked hostnames, either inside or outside the input's own zone."""
    reference = Reference.from_str(input_ooi["primary_key"])

    # webpage-capture also runs on IPAddressHTTPURL. There is no hostname there, so there
    # is no zone for a link to be inside or outside of, and nothing to compare against.
    if reference.class_ != "HostnameHTTPURL":
        return

    network = Network(name=reference.tokenized.netloc.network.name).reference
    own_hostname = reference.tokenized.netloc.name
    own_zone = registrable_domain(own_hostname)
    seen = {own_hostname}

    for hostname in sorted(hostnames_from_capture(raw)):
        # Relative hrefs and bare fragments resolve to the page's own host. That is the
        # input OOI, so re-emitting it would be noise rather than a discovery.
        if hostname in seen:
            continue

        zone = registrable_domain(hostname)

        # A bare public suffix, or anything tldextract cannot place, has no owner to
        # attribute it to.
        if not zone or (zone == own_zone) is external:
            continue

        for name in dict.fromkeys([zone, hostname]):
            if name in seen:
                continue

            # The name survived idna encoding but can still be one the model rejects --
            # an underscore, or a label over 63 characters. Skip that link rather than
            # lose the page.
            try:
                # An apex is minted bare; pointing its registered_domain at itself would
                # be a self-referencing edge for no gain.
                apex = None if name == zone else Hostname(network=network, name=zone).reference
                ooi = Hostname(network=network, name=name, registered_domain=apex)
            except (ValidationError, ValueError, UnicodeError):
                logger.info("Skipping linked hostname that is not a valid Hostname: %s", name)
                continue

            seen.add(name)
            yield ooi
