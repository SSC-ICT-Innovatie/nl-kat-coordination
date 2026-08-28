import ipaddress
import json
import logging
from collections.abc import Iterable, Iterator

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import OOI, Reference
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, IPPort, Network, PortState, Protocol


def get_ip_ports_and_service(ip_with_ports: dict, network: Network, netblock: Reference) -> Iterator[OOI]:
    """Yields IPs and open ports for any ports open on this host."""
    if "ip" not in ip_with_ports:
        raise ValueError("[Masscan] No IP given in output.")
    if "ports" not in ip_with_ports:
        raise ValueError("[Masscan] No ports argument in IP with ports list.")
    host_ip = ip_with_ports["ip"]
    ip_version = ipaddress.ip_interface(host_ip).ip.version
    ip = (
        IPAddressV4(network=network.reference, address=host_ip, netblock=netblock)
        if ip_version == 4
        else IPAddressV6(network=network.reference, address=host_ip, netblock=netblock)
    )
    yield ip

    for port_dict in ip_with_ports["ports"]:
        ip_port = IPPort(
            address=ip.reference,
            protocol=Protocol(port_dict["proto"]),
            port=port_dict["port"],
            state=PortState(port_dict["status"]),
        )
        yield ip_port


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    """Parse Masscan JSON and yield relevant network, IPs and ports."""
    try:
        results = json.loads(raw) if raw else []
    except json.decoder.JSONDecodeError:
        # Masscan tends to forget to close the json with "]" if the wait window passed.
        results = json.loads(raw.decode() + "]") if raw else []

    # Relevant network object is received from the normalizer_meta.
    network = Network(name=input_ooi["network"]["name"])

    netblock_ref = Reference.from_str(input_ooi["primary_key"])

    logging.info("Parsing %d Masscan IPs for %s.", len(raw), network)
    for ip_with_ports in results:
        yield from get_ip_ports_and_service(ip_with_ports=ip_with_ports, network=network, netblock=netblock_ref)
