import json
import logging
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from boefjes.plugins.kat_snyk import check_version
from octopoes.models import Reference
from octopoes.models.ooi.findings import CVEFindingType, Finding, KATFindingType, RiskLevelSeverity, SnykFindingType

logger = logging.getLogger(__name__)

_SEVERITY_MAP = {
    "critical": RiskLevelSeverity.CRITICAL,
    "high": RiskLevelSeverity.HIGH,
    "medium": RiskLevelSeverity.MEDIUM,
    "low": RiskLevelSeverity.LOW,
}


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    results = json.loads(raw)

    pk_ooi = Reference.from_str(input_ooi["primary_key"])
    # Depending on the input type of the boefje, our input_ooi is either a software, or softwareinstance.
    if "software" in input_ooi:
        software_name = input_ooi["software"]["name"]
        software_version = input_ooi["software"]["version"]
    else:
        software_name = input_ooi["name"]
        software_version = input_ooi["version"]

    vulnerabilities = results.get("vulnerabilities", [])
    latest_version = results.get("latest_version")

    if not vulnerabilities:
        if not latest_version:
            logger.warning("Couldn't find software %s in the SNYK vulnerability database", software_name)
        return

    if software_version:
        for vuln in vulnerabilities:
            severity = _SEVERITY_MAP.get(vuln.get("severity", "").lower())
            cvss_score = vuln.get("cvss_score")

            cve = vuln.get("cve")
            if cve and cve.startswith("CVE-"):
                ft = CVEFindingType(id=cve, risk_severity=severity, risk_score=cvss_score)
            else:
                ft = SnykFindingType(id=vuln["id"], risk_severity=severity, risk_score=cvss_score)
            yield ft
            yield Finding(finding_type=ft.reference, ooi=pk_ooi, description=vuln["title"])
    else:
        kat_ooi = KATFindingType(id="KAT-SOFTWARE-VERSION-NOT-FOUND")
        yield kat_ooi
        yield Finding(
            finding_type=kat_ooi.reference,
            ooi=pk_ooi,
            description="There was no version found for this software. "
            "But there are known vulnerabilities for some versions.",
        )

    # Check for latest version
    if software_version and latest_version and check_version.check_version_in(software_version, f"<{latest_version}"):
        kat_ooi = KATFindingType(id="KAT-SOFTWARE-UPDATE-AVAILABLE")
        yield kat_ooi
        yield Finding(
            finding_type=kat_ooi.reference,
            ooi=pk_ooi,
            description=f"You may want to update to the newest version. Your current version is {software_version} "
            f"while the latest version is {latest_version}",
        )
