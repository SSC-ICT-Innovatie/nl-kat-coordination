from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    network_reference = Network(name="internet").reference  # subfinder only sees the internet

    for hostname in raw.decode().splitlines():
        hostname_ooi = Hostname(name=hostname, network=network_reference)
        yield hostname_ooi
