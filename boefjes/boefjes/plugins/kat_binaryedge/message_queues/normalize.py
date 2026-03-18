import ipaddress
import json
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, IPPort, Network, PortState, Protocol
from octopoes.models.ooi.software import Software


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    results = json.loads(raw)
    pk_ooi = Reference.from_str(input_ooi["primary_key"])
    network = Network(name="internet").reference

    # Structure based on https://docs.binaryedge.io/modules/<accepted_modules_name>/
    accepted_modules = "mqtt"
    for scan in results["results"]:
        module = scan["origin"]["type"]
        if module not in accepted_modules:
            continue

        port_nr = int(scan["target"]["port"])
        protocol = scan["target"]["protocol"]
        ip = scan["target"]["ip"]

        if input_ooi["object_type"] in ["IPAddressV4", "IPAddressV6"]:
            ip_ref = pk_ooi
        else:
            ipvx = ipaddress.ip_address(ip)
            if ipvx.version == 4:
                ip_ooi = IPAddressV4(address=ip, network=network)
            else:
                ip_ooi = IPAddressV6(address=ip, network=network)
            yield ip_ooi
            ip_ref = ip_ooi.reference

        ip_port_ooi = IPPort(address=ip_ref, protocol=Protocol(protocol), port=port_nr, state=PortState("open"))
        yield ip_port_ooi

        software_ooi = Software(name=module)
        yield software_ooi
        software_instance_ooi = Software(ooi=ip_port_ooi.reference, software=software_ooi.reference)
        yield software_instance_ooi

        kat_ooi = KATFindingType(id="KAT-EXPOSED-SOFTWARE")
        yield kat_ooi
        yield Finding(
            finding_type=kat_ooi.reference,
            ooi=software_instance_ooi.reference,
            description=f"{module.upper()} should not be exposed to the internet.",
        )
