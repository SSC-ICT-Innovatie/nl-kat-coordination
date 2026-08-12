import json
import re
from collections.abc import Iterable
from typing import Any

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.software import Software, SoftwareInstance

MISSING_HEADER_TO_KAT_FINDING_TYPE = {
    "strict-transport-security": "KAT-HSTS-VULNERABILITIES",
    "x-content-type-options": "KAT-NO-X-CONTENT-TYPE-OPTIONS",
    "content-security-policy": "KAT-CSP-VULNERABILITIES",
    "referrer-policy": "KAT-NO-REFERRER-POLICY",
    "permissions-policy": "KAT-NO-PERMISSIONS-POLICY",
}

# Nikto vulnerability IDs dispatched to the "missing security header" branch.
# Covers both legacy (013587) and Nikto 2.6+ plugin IDs.
MISSING_HEADER_IDS = {"013587", "999100", "999103", "999984"}

# HSTS-specific finding, kept separate so its msg doesn't run through the header regex.
HSTS_IDS = {"999970"}

# HTTP TRACE method enabled / XST exposure.
TRACE_METHOD_IDS = {"000434"}

# Nikto 2.6 "Allowed HTTP Methods" notice — only a finding when TRACE is among them.
ALLOWED_METHODS_ID = "999990"

# Wildcard TLS certificate in use.
WILDCARD_CERT_IDS = {"999992"}

# Known default file exposed (e.g. /icons/README on Apache).
DEFAULT_FILE_IDS = {"003584"}

# Server banner / disclosure headers (x-powered-by, Server:, etc.) — useful for SoftwareInstance.
BANNER_DISCLOSURE_IDS = {"999986"}

# Matches the outdated-software wording Nikto uses, e.g. in the message
# Apache/2.4.49 appears to be outdated (current is at least 2.4.66).
OUTDATED_SOFTWARE_RE = re.compile(r"^([\w.\-]+)/([\w.\-]+)\s+appears to be outdated")

# Matches software/version disclosed in a response header, e.g. in the message
# Retrieved x-powered-by header: Apache/2.4.49.
BANNER_SOFTWARE_RE = re.compile(r"header:\s+([\w.\-]+)/([\w.\-]+)")

# Missing-header message extractor, tolerant to Nikto 2.5 and 2.6+ wording.
MISSING_HEADER_NEW_RE = re.compile(r"missing:\s+([A-Za-z-]+)", re.IGNORECASE)
MISSING_HEADER_OLD_RE = re.compile(r"\bThe\s+([A-Za-z-]+)\s+header", re.IGNORECASE)


def _extract_missing_header(msg: str) -> str | None:
    match = MISSING_HEADER_NEW_RE.search(msg) or MISSING_HEADER_OLD_RE.search(msg)
    return match.group(1).lower() if match else None


def _outdated_software(msg: str, ooi_ref: Reference) -> Iterable[NormalizerOutput]:
    match = OUTDATED_SOFTWARE_RE.match(msg)
    if not match:
        yield from _generic_finding(msg, ooi_ref)
        return

    software = Software(name=match.group(1), version=match.group(2))
    software_instance = SoftwareInstance(ooi=ooi_ref, software=software.reference)
    finding_type = KATFindingType(id="KAT-OUTDATED-SOFTWARE")
    yield software
    yield software_instance
    yield finding_type
    yield Finding(finding_type=finding_type.reference, ooi=software_instance.reference, description=msg)


def _missing_header(msg: str, ooi_ref: Reference) -> Iterable[NormalizerOutput]:
    header = _extract_missing_header(msg)
    finding_type_id = MISSING_HEADER_TO_KAT_FINDING_TYPE.get(header) if header else None
    yield from _simple_finding(finding_type_id or "KAT-MISSING-HEADER", msg, ooi_ref)


def _banner_disclosed(msg: str, ooi_ref: Reference) -> Iterable[NormalizerOutput]:
    match = BANNER_SOFTWARE_RE.search(msg)
    if match:
        software = Software(name=match.group(1), version=match.group(2))
        software_instance = SoftwareInstance(ooi=ooi_ref, software=software.reference)
        yield software
        yield software_instance
    yield from _generic_finding(msg, ooi_ref)


def _simple_finding(finding_type_id: str, msg: str, ooi_ref: Reference) -> Iterable[NormalizerOutput]:
    finding_type = KATFindingType(id=finding_type_id)
    yield finding_type
    yield Finding(finding_type=finding_type.reference, ooi=ooi_ref, description=msg)


def _generic_finding(msg: str, ooi_ref: Reference) -> Iterable[NormalizerOutput]:
    yield from _simple_finding("KAT-NIKTO-FINDING", msg, ooi_ref)


def scan_nikto_output(data: list[dict[str, Any]], ooi_ref: Reference) -> Iterable[NormalizerOutput]:
    for scan in data:
        for vulnerability in scan.get("vulnerabilities", []):
            vulnerability_id = str(vulnerability.get("id", ""))
            msg = str(vulnerability.get("msg", ""))

            if vulnerability_id.startswith("6"):
                yield from _outdated_software(msg, ooi_ref)
            elif vulnerability_id in MISSING_HEADER_IDS:
                yield from _missing_header(msg, ooi_ref)
            elif vulnerability_id in HSTS_IDS:
                yield from _simple_finding("KAT-HSTS-VULNERABILITIES", msg, ooi_ref)
            elif (
                vulnerability_id in TRACE_METHOD_IDS
                or vulnerability_id == ALLOWED_METHODS_ID
                and "TRACE" in msg.upper()
            ):
                yield from _simple_finding("KAT-HTTP-TRACE-METHOD", msg, ooi_ref)
            elif vulnerability_id in WILDCARD_CERT_IDS:
                yield from _simple_finding("KAT-WILDCARD-CERTIFICATE", msg, ooi_ref)
            elif vulnerability_id in DEFAULT_FILE_IDS:
                yield from _simple_finding("KAT-EXPOSED-DEFAULT-FILE", msg, ooi_ref)
            elif vulnerability_id in BANNER_DISCLOSURE_IDS:
                yield from _banner_disclosed(msg, ooi_ref)
            else:
                # Never silently drop a Nikto finding — emit a generic finding so the
                # signal reaches reports and the UI even for IDs we haven't mapped yet.
                yield from _generic_finding(msg, ooi_ref)


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    data = json.loads(raw)
    ooi_ref = Reference.from_str(input_ooi["primary_key"])
    yield from scan_nikto_output(data, ooi_ref)
