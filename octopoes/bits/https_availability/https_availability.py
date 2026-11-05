from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.network import IPAddress, IPPort


def run(input_ooi: IPAddress, additional_oois: list[IPPort], config: dict[str, Any]) -> Iterator[OOI]:
    """HTTP open but HTTPS closed on the same address. The finding binds to
    the address: by definition the pair (80 open, 443 closed) has no
    website object to bind to — nothing serves a name over TLS yet. The
    description comes from the finding type's registry entry."""
    open_ports = [port.port for port in additional_oois if isinstance(port, IPPort)]
    if 80 in open_ports and 443 not in open_ports:
        ft = KATFindingType(id="KAT-HTTPS-NOT-AVAILABLE")
        yield ft
        yield Finding(ooi=input_ooi.reference, finding_type=ft.reference)
