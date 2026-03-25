import logging
from collections.abc import Iterable, Iterator

from libnmap.objects import NmapHost, NmapService
from libnmap.parser import NmapParser

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import OOI, Reference
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, IPPort, Network, PortState, Protocol
from octopoes.models.ooi.service import IPService, Service


def get_ip_ports_and_service(host: NmapHost, network: Network, netblock: Reference | None) -> Iterator[OOI]:
    """Yields IPs, open ports and services if any ports are open on this host."""
    open_ports = host.get_open_ports()
    if open_ports:
        ip = (
            IPAddressV4(network=network.reference, address=host.address, netblock=netblock)
            if host.ipv4
            else IPAddressV6(network=network.reference, address=host.address, netblock=netblock)
        )

        for port, protocol in open_ports:
            service: NmapService = host.get_service(port, protocol)

            # If service is tcpwrapped we should consider the port closed
            if service.service == "tcpwrapped":
                continue

            ip_port = IPPort(
                address=ip.reference, protocol=Protocol(protocol), port=port, state=PortState(service.state)
            )
            yield ip_port

            service_name = service.service
            if service.tunnel == "ssl":
                if service_name == "http":
                    service_name = "https"
                elif service_name == "smtp":
                    service_name = "smtps"
                elif service_name == "imap":
                    service_name = "imaps"
                elif service_name == "pop3":
                    service_name = "pop3s"
                elif service_name == "ftp":
                    service_name = "ftps"

            port_service = Service(name=service_name)
            yield port_service

            ip_service = IPService(ip_port=ip_port.reference, service=port_service.reference)
            yield ip_service


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    """Decouple and parse Nmap XMLs and yield relevant network."""
    # Multiple XMLs are concatenated through "\n\n". XMLs end with "\n"; we split on "\n\n\n".
    raw_splitted = raw.decode().split("\n\n\n")

    # Relevant network object is received from the normalizer_meta.
    network = Network(name=input_ooi["network"]["name"])

    netblock_ref = None
    if "NetBlock" in input_ooi["object_type"]:
        netblock_ref = Reference.from_str(input_ooi["primary_key"])

    logging.info("Parsing %d Nmap-xml(s) for %s.", len(raw_splitted), network)
    for r in raw_splitted:
        for host in NmapParser.parse_fromstring(r).hosts:
            yield from get_ip_ports_and_service(host=host, network=network, netblock=netblock_ref)
