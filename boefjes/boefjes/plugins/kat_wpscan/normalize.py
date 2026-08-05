import json
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import CVEFindingType, Finding, KATFindingType
from octopoes.models.ooi.software import Software, SoftwareInstance


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    url_reference = Reference.from_str(input_ooi["primary_key"])
    if not raw:
        return

    data = json.loads(raw.decode())

    # WordPress core.
    core = data.get("version") or {}
    yield from _handle_component("WordPress", core.get("number"), core.get("vulnerabilities"), False, url_reference)

    # Themes and plugins. wpscan keys these by slug; each carries its own
    # version, outdated flag and vulnerabilities.
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
        yield from _handle_component(
            slug, version_number, component.get("vulnerabilities"), bool(component.get("outdated")), url_reference
        )


def _handle_component(
    name: str, version_number, vulnerabilities, outdated: bool, url_reference: Reference
) -> Iterable[NormalizerOutput]:
    """Yield the Software inventory and the findings for one WordPress component.

    Previously only vulnerabilities carrying a CVE were surfaced (via a
    text-rendering library), so the software inventory, the outdated flag and
    every non-CVE WordPress vulnerability were dropped.
    """
    # Bind findings to the component's SoftwareInstance when we know its version,
    # otherwise to the scanned URL.
    finding_ooi = url_reference
    if version_number:
        software = Software(name=name, version=str(version_number))
        yield software
        software_instance = SoftwareInstance(ooi=url_reference, software=software.reference)
        yield software_instance
        finding_ooi = software_instance.reference

        if outdated:
            outdated_type = KATFindingType(id="KAT-OUTDATED-SOFTWARE")
            yield outdated_type
            yield Finding(
                finding_type=outdated_type.reference,
                ooi=finding_ooi,
                description=f"{name} {version_number} is outdated.",
            )

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
                yield Finding(finding_type=cve_type.reference, ooi=finding_ooi, description=title)
        else:
            # WPScan/WPVulnDB vulnerabilities frequently have no CVE; surface
            # them instead of dropping them.
            vuln_type = KATFindingType(id="KAT-VULNERABLE-SOFTWARE-VERSION")
            yield vuln_type
            yield Finding(finding_type=vuln_type.reference, ooi=finding_ooi, description=title)
