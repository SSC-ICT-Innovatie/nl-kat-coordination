import re
from collections.abc import Iterable
from dataclasses import dataclass

from bs4 import BeautifulSoup

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models.ooi.identifier import Identifier, IdentifierInstance, IdentifierVendor

IDENTIFIER_PATTERNS = {
    "GoogleTagManager": [re.compile(r"\bGTM-[A-Z0-9]+\b")],
    "GoogleAnalytics": [re.compile(r"\bUA-\d+-\d+\b"), re.compile(r"\bG-[A-Z0-9]{6,}\b")],
    "GoogleAds": [re.compile(r"\bAW-\d+\b")],
    "GoogleFloodlight": [re.compile(r"\bDC-\d+\b")],
    "FacebookPixel": [re.compile(r"fbq\s*\(\s*['\"]init['\"]\s*,\s*['\"](\d{5,})['\"]", re.I)],
    "LinkedInInsightTag": [re.compile(r"_linkedin_partner_id\s*=\s*['\"](\d+)['\"]", re.I)],
    "MicrosoftClarity": [re.compile(r"clarity\.ms/tag/([a-z0-9]+)", re.I)],
    "Hotjar": [re.compile(r"hjid\s*:\s*(\d+)", re.I)],
    "Hubspot": [re.compile(r"portalId\s*[:=]\s*['\"]?(\d+)", re.I)],
    "Marketo": [re.compile(r"munchkinId\s*[:=]\s*['\"]([A-Z0-9-]+)", re.I)],
    "Intercom": [re.compile(r"app_id\s*[:=]\s*['\"]([a-z0-9]+)", re.I)],
    "Segment": [re.compile(r"analytics\.load\(\s*['\"]([^'\"]+)['\"]", re.I)],
    "Sentry": [re.compile(r"https://([^@]+@sentry\.io/\d+)", re.I)],
    "GoogleMapsApiKey": [re.compile(r"AIza[0-9A-Za-z\-_]{20,}")],
    "Mapbox": [re.compile(r"pk\.[A-Za-z0-9._\-]+")],
    "FirebaseProjectId": [re.compile(r'"projectId"\s*:\s*"([^"]+)"', re.I)],
    "Matomo": [re.compile(r"setSiteId['\"]?\s*,\s*['\"](\d+)['\"]", re.I)],
    "Crisp": [re.compile(r"CRISP_WEBSITE_ID\s*=\s*['\"]([a-f0-9\-]+)", re.I)],
    "Drift": [re.compile(r"drift\.load\(\s*['\"]([a-z0-9]+)['\"]", re.I)],
    "TawkTo": [re.compile(r"embed\.tawk\.to/([^/]+)/", re.I)],  # codespell:ignore tawk
    "Zendesk": [re.compile(r"https://([a-z0-9\-]+)\.zendesk\.com", re.I)],
    "Tealium": [re.compile(r"utag/([^/]+)/([^/]+)/", re.I)],
}


@dataclass(frozen=True)
class IdentifierMatch:
    vendor: str
    identifier: str


def build_search_text(soup: BeautifulSoup, raw_html: str) -> str:
    chunks = [raw_html]

    for script in soup.find_all("script"):
        if script.string:
            chunks.append(script.string)

        if src := script.get("src"):
            chunks.append(src)

    for tag in soup.find_all(src=True):
        chunks.append(tag["src"])

    for tag in soup.find_all(href=True):
        chunks.append(tag["href"])

    return "\n".join(chunks)


def extract_identifiers(text: str) -> set[IdentifierMatch]:
    found = set()

    for vendor, patterns in IDENTIFIER_PATTERNS.items():
        for pattern in patterns:
            for match in pattern.finditer(text):
                if match.groups():
                    identifier = ":".join(group for group in match.groups() if group is not None)
                else:
                    identifier = match.group(0)

                found.add(IdentifierMatch(vendor=vendor, identifier=identifier))

    return found


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    html = raw.decode(errors="ignore")
    soup = BeautifulSoup(raw, "html.parser")

    search_text = build_search_text(soup, html)

    for match in extract_identifiers(search_text):
        vendor = IdentifierVendor(name=match.vendor)

        identifier = Identifier(vendor=vendor.reference, value=match.identifier)

        yield vendor
        yield identifier

        yield IdentifierInstance(identifier=identifier.reference, usage=input_ooi["reference"])
