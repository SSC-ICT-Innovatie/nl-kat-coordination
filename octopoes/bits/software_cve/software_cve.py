import json
import re
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.findings import CVEFindingType, Finding
from octopoes.models.ooi.software import Software, SoftwareInstance
from packaging.version import InvalidVersion, parse


def run(input_ooi: Software, additional_oois: list[SoftwareInstance], config: dict[str, Any]) -> Iterator[OOI]:
    """Check server software against a curated database of known critical vulnerabilities.

    Unlike retire-js (which covers JavaScript libraries), this bit covers server software
    detected by nmap, dns-version, service-banner, shodan, censys, etc. The database is
    a static JSON file curated for high-impact CVEs — it is not comprehensive. Software
    without a version is skipped, since we cannot match version ranges.
    """
    if not input_ooi.version:
        return

    vulnerabilities = _check_vulnerabilities(input_ooi.name, input_ooi.version)
    for cve_id, summary in vulnerabilities:
        for instance in additional_oois:
            ft = CVEFindingType(id=cve_id)
            yield ft
            yield Finding(
                finding_type=ft.reference,
                ooi=instance.reference,
                description=f"{cve_id}: {summary} (affecting {input_ooi.name} {input_ooi.version})",
            )


@lru_cache(maxsize=1)
def _load_database() -> dict:
    path = Path(__file__).parent / "software_vulnerabilities.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _process_name(name: str) -> str:
    return name.lower().replace(" ", "").replace("_", "").replace("-", "").replace(".", "")


def _check_vulnerabilities(name: str, version: str) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    processed_name = _process_name(name)
    database = _load_database()

    for db_name, entry in database.items():
        if processed_name != _process_name(db_name):
            continue
        for vuln in entry["vulnerabilities"]:
            if _version_matches(version, vuln):
                cves = vuln["identifiers"].get("CVE", [])
                summary = vuln["identifiers"].get("summary", "")
                for cve in cves:
                    results.append((cve, summary))
    return results


_TRAILING_LETTER_RE = re.compile(r"^(\d+(?:\.\d+)*)([a-zA-Z]+)$")


def _split_version(version: str) -> tuple[str, str]:
    """Split a version into (numeric_base, letter_suffix).

    Handles non-semver schemes like OpenSSL's 1.0.1f where the trailing
    letter is a patch level, not a pre-release marker.
    """
    m = _TRAILING_LETTER_RE.match(version.strip())
    if m:
        return m.group(1), m.group(2).lower()
    return version.strip(), ""


def _version_matches(version: str, vuln: dict) -> bool:
    base, letter = _split_version(version)
    below_base, below_letter = _split_version(vuln["below"])

    try:
        if parse(base) > parse(below_base):
            return False
        if parse(base) == parse(below_base) and letter >= below_letter:
            return False
    except InvalidVersion:
        return False

    if "atOrAbove" in vuln:
        at_base, at_letter = _split_version(vuln["atOrAbove"])
        try:
            if parse(base) < parse(at_base):
                return False
            if parse(base) == parse(at_base) and letter < at_letter:
                return False
        except InvalidVersion:
            return False

    return True
