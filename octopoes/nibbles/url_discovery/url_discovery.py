from collections.abc import Iterator

from octopoes.models import OOI
from octopoes.models.ooi.dns.zone import ResolvedHostname
from octopoes.models.ooi.network import IPPort, Network
from octopoes.models.ooi.web import URL


def nibble(ip_port: IPPort, resolved_hostname: ResolvedHostname) -> Iterator[OOI]:
    yield URL(
        network=Network(name=resolved_hostname.hostname.tokenized.network.name).reference,
        raw=f"{'https' if ip_port.port == 443 else 'http'}://{resolved_hostname.hostname.tokenized.name}/",
    )
