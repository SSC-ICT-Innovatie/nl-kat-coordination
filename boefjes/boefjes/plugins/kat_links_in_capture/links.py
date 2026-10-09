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
"""

import json
from collections.abc import Iterable
from urllib.parse import urljoin, urlparse

import tldextract
from bs4 import BeautifulSoup

from boefjes.normalizer_models import NormalizerOutput
from boefjes.plugins.kat_wappalyzer.har_zip import har_from_playwright_zip
from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network

# tldextract consults only the ICANN section of the public suffix list by default, which
# collapses every tenant of a shared platform onto the platform itself: `a.github.io` and
# `b.github.io` would both come out as `github.io`. Including the private section keeps
# them apart, so that "same registrable domain" keeps meaning "same owner" -- which is
# the whole basis for inheriting clearance below.
_EXTRACT = tldextract.TLDExtract(include_psl_private_domains=True)


def registrable_domain(hostname: str) -> str:
    return _EXTRACT(hostname).top_domain_under_public_suffix


def _document_entry(har: dict) -> dict | None:
    """The first HAR entry that actually carries an HTML body.

    Not simply the first entry: a redirect is an HTML content type with an empty body,
    so a site that redirects would otherwise yield nothing.
    """
    for entry in har.get("log", {}).get("entries", []):
        content = entry.get("response", {}).get("content", {})
        if "html" in (content.get("mimeType") or "") and content.get("text"):
            return entry

    return None


def hostnames_from_capture(raw: bytes) -> set[str]:
    """Hostnames behind the `<a href>` links in the captured document."""
    entry = _document_entry(json.loads(har_from_playwright_zip(raw)))

    if entry is None:
        return set()

    base = entry.get("request", {}).get("url", "")
    soup = BeautifulSoup(entry["response"]["content"]["text"], "html.parser")
    hostnames = set()

    for anchor in soup.find_all("a", href=True):
        # Relative hrefs are the common case, and mailto:, tel: and javascript: links
        # resolve to a scheme we drop below rather than to a host.
        parsed = urlparse(urljoin(base, anchor["href"].strip()))

        if parsed.scheme in ("http", "https") and parsed.hostname:
            hostnames.add(parsed.hostname.lower())

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
    seen_apexes = set()

    for hostname in sorted(hostnames_from_capture(raw)):
        # Relative hrefs and bare fragments resolve to the page's own host. That is the
        # input OOI, so re-emitting it would be noise rather than a discovery.
        if hostname == own_hostname:
            continue

        zone = registrable_domain(hostname)

        # A bare public suffix, or anything tldextract cannot place, has no owner to
        # attribute it to.
        if not zone:
            continue

        if (zone == own_zone) is external:
            continue

        apex = Hostname(network=network, name=zone)
        if zone not in seen_apexes:
            seen_apexes.add(zone)
            yield apex

        # An apex links to itself often enough; pointing its registered_domain at itself
        # would be a self-referencing edge for no gain.
        if hostname != zone:
            yield Hostname(network=network, name=hostname, registered_domain=apex.reference)
