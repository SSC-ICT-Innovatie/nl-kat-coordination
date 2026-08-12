import ipaddress
import json
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, IPPort, Network, PortState, Protocol
from octopoes.models.ooi.service import IPService, Service


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    results = json.loads(raw)
    pk_ooi = Reference.from_str(input_ooi["primary_key"])
    network = Network(name="internet").reference

    # Structure based on https://docs.binaryedge.io/modules/<accepted_modules_name>/
    accepted_modules = ("rdp", "rdpeudp", "vnc", "x11", "bluekeep")
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

        service_name = ""
        if module == "rdp" and scan.get("result", {}).get("data", {}).get("security", "").lower() == "ssl":
            service_name = "ssl/rdp"
        elif module == "rdp" or module == "rdpeudp" or module == "bluekeep":
            service_name = "rdp"
        elif module == "vnc" or module == "x11":
            service_name = module

        service_ooi = Service(name=service_name)
        yield service_ooi

        ip_service_ooi = IPService(ip_port=ip_port_ooi.reference, service=service_ooi.reference)
        yield ip_service_ooi

        kat_641_ooi = KATFindingType(id="KAT-EXPOSED-SOFTWARE")
        yield kat_641_ooi
        yield Finding(
            finding_type=kat_641_ooi.reference,
            ooi=ip_service_ooi.reference,
            description=f"{module.upper()} should not be exposed to the internet.",
        )

        if module == "bluekeep" and scan.get("result", {}).get("data", {}).get("status", "").lower() == "vulnerable":
            kat_642_ooi = KATFindingType(id="KAT-VERIFIED-VULNERABILITY")
            yield kat_642_ooi
            yield Finding(
                finding_type=kat_642_ooi.reference,
                ooi=ip_service_ooi.reference,
                description="It is verified that this Remote Desktop server is vulnerable to the Bluekeep "
                "vulnerability.",
            )
