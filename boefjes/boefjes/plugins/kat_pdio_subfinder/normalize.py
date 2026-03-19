from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    hostname_ooi_reference = Reference.from_str(input_ooi["primary_key"])
    network_reference = Network(name=hostname_ooi_reference.tokenized.network.name).reference

    for hostname in raw.decode().splitlines():
        hostname_ooi = Hostname(name=hostname, network=network_reference)
        yield hostname_ooi
