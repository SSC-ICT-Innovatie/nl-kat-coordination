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
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network
from octopoes.models.ooi.software import Software, SoftwareInstance
from octopoes.models.ooi.web import HostnameHTTPURL


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    pk = input_ooi["primary_key"]
    tokenized_weburl = Reference.from_str(pk).tokenized["web_url"]
    tokenized_hostname = Reference.from_str(pk).tokenized["website"]["hostname"]

    network = Network(name=tokenized_hostname["network"]["name"])
    hostname = Hostname(network=network.reference, name=tokenized_hostname["name"])
    web_url = HostnameHTTPURL(
        network=network.reference,
        netloc=hostname.reference,
        port=tokenized_weburl["port"],
        scheme=tokenized_weburl["scheme"],
        path=tokenized_weburl["path"],
    )

    data_directory = Path(__file__).parent / "data"
    fingerprints = Fingerprints.model_validate_pattern(data_directory.joinpath("technologies/*.json").as_posix())
    categories = Categories.model_validate_file(data_directory.joinpath("categories.json"))
    groups = Groups.model_validate_file(data_directory.joinpath("groups.json"))
    httpx.HTTPTransport()
    har = Har.model_validate_json(raw)

    wappalyzer = Wappalyzer(fingerprints, categories=categories, groups=groups)

    analyzes = [analyze_scripts, analyze_css]

    # check if the content type is html
    if har.log.entries and is_html(har.log.entries[0]):
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
        software_instance = SoftwareInstance(ooi=web_url.reference, software=software.reference)
        yield from [software, software_instance]


# analyze_scripts is used to check javascript files, therefore we need another analyzer that analyzes the script
# source in the html
def analyze_script_src_in_html(har: HarWrapper, fingerprint: schemas.Fingerprint) -> list[Detection]:
    detections: list[Detection] = []

    for pattern in fingerprint.script_src:
        if pattern.regex.search(har.html):
            detections.append(
                Detection(url=har.url, fingerprint=fingerprint, app_type="html", pattern=pattern, value=har.html)
            )

    return detections
