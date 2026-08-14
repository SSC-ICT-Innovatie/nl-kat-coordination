import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.dns.records import DNSTXTRecord
from octopoes.models.ooi.identifier import Identifier, IdentifierInstance, IdentifierVendor

IDENTIFIER_PATTERNS = {
    "GoogleSiteVerification": [re.compile(r"(?:^|\s)google-site-verification=([A-Za-z0-9_-]+)(?:\s|$)", re.I)],
    "MicrosoftDomainVerification": [re.compile(r"(?:^|\s)MS=(ms\d+)(?:\s|$)", re.I)],
    "FacebookDomainVerification": [re.compile(r"(?:^|\s)facebook-domain-verification=([A-Za-z0-9_-]+)(?:\s|$)", re.I)],
    "AppleDomainVerification": [re.compile(r"(?:^|\s)apple-domain-verification=([A-Za-z0-9_-]+)(?:\s|$)", re.I)],
    "PinterestSiteVerification": [re.compile(r"(?:^|\s)pinterest-site-verification=([A-Za-z0-9_-]+)(?:\s|$)", re.I)],
    "AtlassianDomainVerification": [
        re.compile(r"(?:^|\s)atlassian-domain-verification=([A-Za-z0-9_-]+)(?:\s|$)", re.I)
    ],
    "AdobeDomainVerification": [re.compile(r"(?:^|\s)adobe-(?:sign-)?verification=([A-Za-z0-9_-]+)(?:\s|$)", re.I)],
    "DropboxDomainVerification": [re.compile(r"(?:^|\s)dropbox-domain-verification=([A-Za-z0-9_-]+)(?:\s|$)", re.I)],
    "DocusignDomainVerification": [re.compile(r"(?:^|\s)docusign=([A-Za-z0-9_-]+)(?:\s|$)", re.I)],
    "GlobalSignDomainVerification": [
        re.compile(r"(?:^|\s)globalsign-domain-verification=([A-Za-z0-9_-]+)(?:\s|$)", re.I)
    ],
    "ZoomDomainVerification": [re.compile(r"(?:^|\s)ZOOM_verify_([A-Za-z0-9_-]+)(?:\s|$)", re.I)],
}


@dataclass(frozen=True)
class IdentifierMatch:
    vendor: str
    identifier: str


def extract_identifiers(value: str) -> set[IdentifierMatch]:
    found = set()

    for vendor, patterns in IDENTIFIER_PATTERNS.items():
        for pattern in patterns:
            for match in pattern.finditer(value):
                if match.groups():
                    identifier = ":".join(group for group in match.groups() if group is not None)
                else:
                    identifier = match.group(0)

                found.add(IdentifierMatch(vendor=vendor, identifier=identifier))

    return found


def run(record: DNSTXTRecord, additional_oois: list[OOI], config: dict[str, Any]) -> Iterator[OOI]:
    for match in extract_identifiers(record.value):
        vendor = IdentifierVendor(name=match.vendor)

        identifier = Identifier(vendor=vendor.reference, value=match.identifier)

        yield vendor
        yield identifier
        yield IdentifierInstance(identifier=identifier.reference, usage=record.reference)
