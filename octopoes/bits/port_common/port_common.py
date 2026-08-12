from collections.abc import Iterator

from octopoes.models import OOI
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.network import IPPort, Protocol

COMMON_TCP_PORTS = [
    25,  # SMTP
    53,  # DNS
    80,  # HTTP
    110,  # POP3
    143,  # IMAP
    443,  # HTTPS
    465,  # SMTPS
    587,  # SMTP (message submmission)
    993,  # IMAPS
    995,  # POP3S
]

COMMON_UDP_PORTS = [
    53  # DNS
]


def run(input_ooi: IPPort, additional_oois: list, config: dict) -> Iterator[OOI]:
    port = input_ooi.port
    protocol = input_ooi.protocol
    if (protocol == Protocol.TCP and port in COMMON_TCP_PORTS) or (
        protocol == Protocol.UDP and port in COMMON_UDP_PORTS
    ):
        kat = KATFindingType(id="KAT-OPEN-COMMON-PORT")
        yield kat
        yield Finding(
            finding_type=kat.reference,
            ooi=input_ooi.reference,
            description=f"Port {port}/{protocol.value} is a common port and found to be open.",
        )
