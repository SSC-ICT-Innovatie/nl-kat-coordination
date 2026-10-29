import json
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import CVEFindingType, Finding, RiskLevelSeverity, WPVulnFindingType
from octopoes.models.ooi.software import Software, SoftwareInstance

# wpscan reports cvss scores for vulnerabilities; map them to OpenKAT risk
# severities the same way the CVE finding-type normalizer does.
_SEVERITY_SCORE_LOOKUP = {
    RiskLevelSeverity.CRITICAL: 9.0,
    RiskLevelSeverity.HIGH: 7.0,
    RiskLevelSeverity.MEDIUM: 4.0,
    RiskLevelSeverity.LOW: 0.1,
    RiskLevelSeverity.RECOMMENDATION: 0.0,
}


def _risk_severity(score: float | None) -> RiskLevelSeverity:
    if score is None:
        return RiskLevelSeverity.UNKNOWN
    for risk_level, threshold in _SEVERITY_SCORE_LOOKUP.items():
        if score >= threshold:
            return risk_level
    return RiskLevelSeverity.UNKNOWN


def _cvss_score(vulnerability: dict) -> float | None:
    cvss = vulnerability.get("cvss") or {}
    if isinstance(cvss, dict):
        score = cvss.get("score")
    elif isinstance(cvss, str):
        score = cvss
    else:
        score = vulnerability.get("cvss_score")
    if score is None:
        return None
    try:
        return float(score)
    except (TypeError, ValueError):
        return None


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    # The boefje consumes SoftwareInstance, so the input OOI is the
    # SoftwareInstance that triggered the scan. The scanned URL is the `ooi`
    # part of its primary key — strip the leading "SoftwareInstance|" and the
    # trailing "Software|name|version|cpe" segments to recover it. This works
    # for both the serialized shape (token tree, no nested primary_key) and
    # the runner-fallback shape ({"primary_key": ...}).
    pk = input_ooi["primary_key"]
    if pk.startswith("SoftwareInstance|"):
        url_reference = Reference.from_str("|".join(pk[len("SoftwareInstance|") :].split("|")[:-4]))
    else:
        url_reference = Reference.from_str(pk)
    if not raw:
        return

    data = json.loads(raw.decode())

    # WordPress core.
    core = data.get("version") or {}
    yield from _handle_component("WordPress", core.get("number"), core.get("vulnerabilities"), url_reference)

    # Themes and plugins. wpscan keys these by slug; each carries its own
    # version and vulnerabilities.
    components: dict[str, dict] = {}
    main_theme = data.get("main_theme")
    if isinstance(main_theme, dict) and main_theme.get("slug"):
        components[main_theme["slug"]] = main_theme
    components.update(data.get("themes") or {})
    components.update(data.get("plugins") or {})

    for slug, component in components.items():
        if not isinstance(component, dict):
            continue
        version_number = (component.get("version") or {}).get("number")
        yield from _handle_component(slug, version_number, component.get("vulnerabilities"), url_reference)


def _handle_component(
    name: str, version_number, vulnerabilities, url_reference: Reference
) -> Iterable[NormalizerOutput]:
    """Yield the Software inventory and the findings for one WordPress component.

    Findings bind to the component's Software — a CVE/vulnerability is a
    property of the software, not of the software at a specific location; where
    it is installed is inferred via the graph. When no version is detected there
    is no Software, so findings fall back to the scanned URL.

    Each wpscan vulnerability carries a unique WPVulnDB id, so non-CVE
    vulnerabilities become distinct WPVulnFindingType instances and do not
    collapse to a single Finding in Octopoes. wpscan's JSON already carries the
    WPVulnDB metadata (title, cvss), so the finding type is hydrated here.
    """
    software: Software | None = None
    if version_number:
        software = Software(name=name, version=str(version_number))
        yield software
        yield SoftwareInstance(ooi=url_reference, software=software.reference)

    finding_ooi = software.reference if software is not None else url_reference

    for vulnerability in vulnerabilities or []:
        title = vulnerability.get("title")
        cves = (vulnerability.get("references") or {}).get("cve") or []
        if cves:
            for cve in cves:
                cve_id = str(cve).upper()
                if not cve_id.startswith("CVE-"):
                    cve_id = f"CVE-{cve_id}"
                cve_type = CVEFindingType(id=cve_id)
                yield cve_type
                yield Finding(finding_type=cve_type.reference, ooi=finding_ooi, description=title or cve_id)
            continue

        # Non-CVE vulnerability: WPVulnDB carries a unique id per entry, so each
        # becomes its own WPVulnFindingType + Finding (no collapse).
        vuln_id = str(vulnerability.get("id") or "").strip()
        if not vuln_id or not title:
            continue
        cvss_score = _cvss_score(vulnerability)
        wpvuln_type = WPVulnFindingType(
            id=vuln_id,
            description=title,
            risk_score=cvss_score,
            risk_severity=_risk_severity(cvss_score),
            source=f"https://wpscan.com/vulnerability/{vuln_id}",
        )
        yield wpvuln_type
        yield Finding(finding_type=wpvuln_type.reference, ooi=finding_ooi, description=title)
