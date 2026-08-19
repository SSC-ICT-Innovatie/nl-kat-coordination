"""Shared Wappalyzer analysis: turn a HAR into Software / SoftwareInstance OOIs.

Used by both the `kat_wappalyzer` normalizer (static requests HAR from
webpage-analysis) and the `kat_wappalyzer_capture` normalizer (Playwright browser
HAR from webpage-capture). The caller passes the reference the SoftwareInstances
should attach to, so no OOIs are minted for third-party hosts the page loaded.
"""

from collections.abc import Iterable
from pathlib import Path
from typing import cast

import httpx
from tanimachi import (
    Categories,
    Fingerprints,
    Groups,
    Har,
    Wappalyzer,
    analyze_css,
    analyze_headers,
    analyze_scripts,
    analyze_url,
    schemas,
)
from tanimachi.wappalyzer import (
    Detection,
    HarWrapper,
    analyze_cookies,
    analyze_dom,
    analyze_html,
    analyze_meta,
    is_html,
)

from boefjes.normalizer_models import NormalizerOutput
from boefjes.plugins.kat_wappalyzer.utils import replace_cpe_version
from octopoes.models import Reference
from octopoes.models.ooi.software import Software, SoftwareInstance

DATA_DIRECTORY = Path(__file__).parent / "data"


def software_from_har(raw: bytes, target: Reference) -> Iterable[NormalizerOutput]:
    """Yield Software + SoftwareInstance(ooi=target) for each Wappalyzer detection."""
    fingerprints = Fingerprints.model_validate_pattern(DATA_DIRECTORY.joinpath("technologies/*.json").as_posix())
    categories = Categories.model_validate_file(DATA_DIRECTORY.joinpath("categories.json"))
    groups = Groups.model_validate_file(DATA_DIRECTORY.joinpath("groups.json"))
    httpx.HTTPTransport()
    har = Har.model_validate_json(raw)

    wappalyzer = Wappalyzer(fingerprints, categories=categories, groups=groups)

    analyzes = [analyze_scripts, analyze_css]

    # is_html() only checks the Content-Type header; a redirect / Content-Length: 0
    # response can be text/html with no body, so har.html raises inside
    # analyze_html / analyze_dom / analyze_meta / analyze_script_src_in_html.
    first_entry = har.log.entries[0] if har.log.entries else None
    if first_entry and is_html(first_entry) and first_entry.response.content.text:
        analyzes.extend(
            [
                analyze_headers,
                analyze_url,
                analyze_cookies,
                analyze_meta,
                analyze_html,
                analyze_dom,
                analyze_script_src_in_html,
            ]
        )

    detections = cast(list[Detection], wappalyzer.analyze(har, analyzes=analyzes))

    for detection in detections:
        version = None
        cpe = detection.fingerprint.cpe
        if detection.pattern.version:
            version = detection.pattern.regex.search(detection.value).expand(detection.pattern.version)

        if cpe is not None and version is not None:
            cpe = replace_cpe_version(cpe, version)

        software = Software(name=detection.fingerprint.id, version=version, cpe=cpe)
        yield software
        yield SoftwareInstance(ooi=target, software=software.reference)


# analyze_scripts is used to check javascript files, therefore we need another analyzer that analyzes the script
# source in the html
def analyze_script_src_in_html(har: HarWrapper, fingerprint: schemas.Fingerprint) -> list[Detection]:
    detections: list[Detection] = []

    for pattern in fingerprint.script_src:
        try:
            if pattern.regex.search(har.html):
                detections.append(
                    Detection(url=har.url, fingerprint=fingerprint, app_type="html", pattern=pattern, value=har.html)
                )
        except ValueError:  # no html found
            return []
    return detections
