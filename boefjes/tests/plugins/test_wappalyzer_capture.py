from boefjes.plugins.kat_wappalyzer_capture.normalize import run
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network
from octopoes.models.ooi.web import HostnameHTTPURL
from tests.loading import get_dummy_data


def _input_url():
    network = Network(name="internet")
    hostname = Hostname(network=network.reference, name="mispo.es")
    return HostnameHTTPURL(network=network.reference, netloc=hostname.reference, scheme="https", port=443, path="/")


def test_attaches_software_and_versions_to_the_input_url():
    # webpage-capture consumes a HostnameHTTPURL, so SoftwareInstances attach to it
    # directly. A plain HAR is accepted as-is (zip handling is covered separately).
    url = _input_url()
    results = list(run({"primary_key": str(url.reference)}, get_dummy_data("download_page_analysis.raw")))

    software = [o for o in results if o.object_type == "Software"]
    instances = [o for o in results if o.object_type == "SoftwareInstance"]

    assert software, "expected Wappalyzer detections"
    assert instances and all(str(instance.ooi) == str(url.reference) for instance in instances)
    # Versions coming through is the whole point of running over the rendered HAR (#4447).
    assert any(o.version for o in software)


def test_no_third_party_host_or_url_oois_are_minted():
    # Scan-level scoping (per #3916 discussion): only Software/SoftwareInstance,
    # never a Hostname/URL for a third-party host the page referenced.
    url = _input_url()
    results = list(run({"primary_key": str(url.reference)}, get_dummy_data("download_page_analysis.raw")))

    assert {o.object_type for o in results} <= {"Software", "SoftwareInstance"}
