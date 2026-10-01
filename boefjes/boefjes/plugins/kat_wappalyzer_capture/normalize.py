from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from boefjes.plugins.kat_wappalyzer.analysis import software_from_har
from boefjes.plugins.kat_wappalyzer.har_zip import har_from_playwright_zip
from octopoes.models import Reference


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    # webpage-capture consumes a HostnameHTTPURL / IPAddressHTTPURL, so the input
    # OOI is the URL the SoftwareInstances attach to directly. The browser HAR is
    # a Playwright zip; har_from_playwright_zip inlines its bodies for tanimachi.
    target = Reference.from_str(input_ooi["primary_key"])

    yield from software_from_har(har_from_playwright_zip(raw), target)
