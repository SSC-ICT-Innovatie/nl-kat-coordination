from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import CVEFindingType, Finding
from octopoes.models.ooi.software import Software, SoftwareInstance
from packaging.version import Version, parse

VULNERABLE_RANGES: list[tuple[str, str]] = [("0", "11.8.1.1"), ("11.9.0.0", "11.9.1.1"), ("11.10.0.0", "11.10.0.2")]


def extract_js_version(html_content: str) -> Version | bool:
    telltale = "/mifs/scripts/auth.js?"
    telltale_position = html_content.find(telltale)
    if telltale_position == -1:
        return False
    version_end = html_content.find('"', telltale_position)
    if version_end == -1:
        return False
    version_string = html_content[telltale_position + len(telltale) : version_end]
    if not version_string:
        return False
    return parse(" ".join(strip_vsp_and_build(version_string)))


def extract_css_version(html_content: str) -> Version | bool:
    telltale = "/mifs/css/windowsAllAuth.css?"
    telltale_position = html_content.find(telltale)
    if telltale_position == -1:
        return False
    version_end = html_content.find('"', telltale_position)
    if version_end == -1:
        return False
    version_string = html_content[telltale_position + len(telltale) : version_end]
    if not version_string:
        return False
    return parse(" ".join(strip_vsp_and_build(version_string)))


def strip_vsp_and_build(url: str) -> Iterable[str]:
    url_parts = url.split()
    for part in url_parts:
        if str(part).lower() == "vsp":
            continue
        if str(part).lower() == "build":
            break
        yield part


def is_vulnerable_version(vulnerable_ranges: list[tuple[Version, Version]], detected_version: Version) -> bool:
    return any(start <= detected_version < end for start, end in vulnerable_ranges)


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    ooi = Reference.from_str(input_ooi["primary_key"])
    html = raw.decode()
    js_detected_version = extract_js_version(html)
    css_detected_version = extract_css_version(html)
    if not js_detected_version and not css_detected_version:
        return

    if js_detected_version:
        software = Software(name="Ivanti EPMM", version=str(js_detected_version))
    else:
        software = Software(name="Ivanti EPMM", version=str(css_detected_version))
    software_instance = SoftwareInstance(ooi=ooi, software=software.reference)
    yield software
    yield software_instance
    if js_detected_version:
        vulnerable = is_vulnerable_version(
            [(parse(start), parse(end)) for start, end in VULNERABLE_RANGES], js_detected_version
        )
    else:
        # The CSS version only included the first two parts of the version number so we don't know the patch level
        vulnerable = css_detected_version < parse("11.8")
    if vulnerable:
        finding_type = CVEFindingType(id="CVE-2023-35078")
        finding = Finding(
            finding_type=finding_type.reference,
            ooi=software_instance.reference,
            description="Software is most likely vulnerable to CVE-2023-35078",
        )
        yield finding_type
        yield finding
