import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.findings import CVEFindingType, Finding, RetireJSFindingType
from octopoes.models.ooi.software import Software, SoftwareInstance
from packaging.version import parse


def run(input_ooi: Software, additional_oois: list[SoftwareInstance], config: dict[str, Any]) -> Iterator[OOI]:
    software_name = input_ooi.name
    software_version = input_ooi.version if input_ooi.version else "999.9.9"

    filename_path = Path(__file__).parent / "retirejs.json"
    with filename_path.open(encoding="utf-8") as json_file:
        known_vulnerabilities = json.load(json_file)

    vulnerabilities = _check_vulnerabilities(software_name, software_version, known_vulnerabilities)
    for vulnerability in vulnerabilities["CVE"]:
        for instance in additional_oois:
            ft = CVEFindingType(id=vulnerability)
            yield ft
            yield Finding(
                finding_type=ft.reference,
                ooi=instance.reference,
                description="This JavaScript Library has known vulnerabilities",
            )

    for vulnerability in vulnerabilities["RetireJS"]:
        for instance in additional_oois:
            ft = RetireJSFindingType(id=vulnerability)
            yield ft
            yield Finding(
                finding_type=ft.reference,
                ooi=instance.reference,
                description="This JavaScript Library has known vulnerabilities",
            )


def _check_vulnerabilities(name: str, package_version: str, known_vulnerabilities: dict) -> dict[str, list[str]]:
    vulnerabilities: dict[str, list[str]] = {"CVE": [], "RetireJS": []}
    processed_name = _process_name(name)
    found_brands = [brand for brand in known_vulnerabilities if processed_name == _process_name(brand)]

    if found_brands:
        brand = found_brands[0]
        for known_vulnerability in known_vulnerabilities[brand]["vulnerabilities"]:
            if _check_versions(package_version, known_vulnerability):
                identifiers = known_vulnerability["identifiers"]
                if "CVE" in identifiers:
                    vulnerabilities["CVE"].append(identifiers["CVE"][0])
                else:
                    vulnerabilities["RetireJS"].append(f"RetireJS-{processed_name}-{_hash_identifiers(identifiers)}")

    return vulnerabilities


def _process_name(name: str) -> str:
    return name.lower().replace(" ", "").replace("_", "").replace("-", "").replace(".", "")


def _hash_identifiers(identifiers: dict[str, str | list[str]]) -> str:
    pre_hash = ""
    for identifier in identifiers.values():
        pre_hash += "".join(identifier)
    return hashlib.sha1(pre_hash.encode()).hexdigest()[:4]


def _check_versions(package_version: str, known_vulnerability: dict) -> bool:
    below = parse(package_version) < parse(known_vulnerability["below"])
    # Some packages are only vulnerable below a version and not above
    above = (
        parse(package_version) >= parse(known_vulnerability["atOrAbove"])
        if "atOrAbove" in known_vulnerability
        else True
    )
    return below and above
