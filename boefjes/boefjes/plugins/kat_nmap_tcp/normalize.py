import logging
from collections.abc import Iterable, Iterator

from libnmap.objects import NmapHost, NmapService
from libnmap.parser import NmapParser

from boefjes.normalizer_models import NormalizerOutput
from boefjes.plugins.helpers import cpe_to_name_version
from octopoes.models import OOI, Reference
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, IPPort, Network, PortState, Protocol
from octopoes.models.ooi.service import IPService, Service
from octopoes.models.ooi.software import Software, SoftwareInstance


def get_software(service: NmapService, ip_service: IPService) -> Iterator[OOI]:
    """Yield Software/SoftwareInstance from nmap's version detection (-sV).

    nmap emits the detected product/version as CPEs (and as product/version
    attributes). These were previously dropped, so no Software was recorded and
    CVEs could not be bound to the software actually running on a port. We use
    the application CPEs (cpe:/a:...) when present, and otherwise fall back to
    the raw product/version. Operating-system CPEs (cpe:/o:...) are intentionally
    left out here: they describe the host, not the service.
    """
    application_cpes = [cpe.cpestring for cpe in service.cpelist if cpe.cpestring.startswith("cpe:/a:")]
    if application_cpes:
        for cpe in application_cpes:
            name, version = cpe_to_name_version(cpe=cpe)
            if not name:
                continue

            software = Software(name=name, version=version, cpe=cpe)
            yield software
            yield SoftwareInstance(ooi=ip_service.reference, software=software.reference)
        return

    product = service.service_dict.get("product")
    if product:
        software = Software(name=product, version=service.service_dict.get("version") or None)
        yield software
        yield SoftwareInstance(ooi=ip_service.reference, software=software.reference)


def get_ip_ports_and_service(
    host: NmapHost, network: Network, netblock: Reference | None, input_ref: Reference | None
) -> Iterator[OOI]:
    open_ports = host.get_open_ports()

    ip = (
        IPAddressV4(network=network.reference, address=host.address, netblock=netblock)
        if host.ipv4
        else IPAddressV6(network=network.reference, address=host.address, netblock=netblock)
    )

    # Never yield the input OOI itself (#2310). With -Pn nmap reports every scanned address as "up",
    # so only yield the IP once it has an open port: otherwise each address of a netblock becomes an IP.
    ip_yielded = input_ref is not None and ip.reference == input_ref

    for port, protocol in open_ports:
        service: NmapService = host.get_service(port, protocol)

        # If service is tcpwrapped we should consider the port closed
        if service.service == "tcpwrapped":
            continue

        if not ip_yielded:
            yield ip
            ip_yielded = True

        ip_port = IPPort(address=ip.reference, protocol=Protocol(protocol), port=port, state=PortState(service.state))
        yield ip_port

        service_name = service.service
        if service.tunnel == "ssl" and service_name in ("http", "smtp", "imap", "pop3", "ftp"):
            service_name = f"{service_name}s"

        port_service = Service(name=service_name)
        yield port_service

        ip_service = IPService(ip_port=ip_port.reference, service=port_service.reference)
        yield ip_service

        yield from get_software(service, ip_service)


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    """Decouple and parse Nmap XMLs and yield relevant network."""
    # Multiple XMLs are concatenated through "\n\n". XMLs end with "\n"; we split on "\n\n\n".
    raw_splitted = raw.decode().split("\n\n\n")

    # Relevant network object is received from the normalizer_meta.
    network = Network(name=input_ooi["network"]["name"])

    input_ref = None
    if "IPAddress" in input_ooi["object_type"]:
        input_ref = Reference.from_str(input_ooi["primary_key"])

    netblock_ref = None
    if "NetBlock" in input_ooi["object_type"]:
        netblock_ref = Reference.from_str(input_ooi["primary_key"])

    logging.info("Parsing %d Nmap-xml(s) for %s.", len(raw_splitted), network)
    for r in raw_splitted:
        for host in NmapParser.parse_fromstring(r).hosts:
            yield from get_ip_ports_and_service(host=host, network=network, netblock=netblock_ref, input_ref=input_ref)
