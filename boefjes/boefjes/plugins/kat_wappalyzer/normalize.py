from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from boefjes.plugins.kat_wappalyzer.analysis import software_from_har
from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network
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

    yield from software_from_har(raw, web_url.reference)
