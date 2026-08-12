import ipaddress
import json
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from boefjes.plugins.helpers import cpe_to_name_version
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, IPPort, Network, PortState, Protocol
from octopoes.models.ooi.service import IPService, Service
from octopoes.models.ooi.software import Software, SoftwareInstance


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    results = json.loads(raw)
    pk_ooi = Reference.from_str(input_ooi["primary_key"])
    network = Network(name="internet").reference

    # Structure based on https://docs.binaryedge.io/modules/<accepted_modules_name>/
    accepted_modules = ("service-simple", "service", "malware-simple")
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

        if "service" in scan["result"]["data"]:
            service = scan["result"]["data"]["service"]
            service_ooi = Service(name=service["name"])
            yield service_ooi

            ip_service_ooi = IPService(ip_port=ip_port_ooi.reference, service=service_ooi.reference)
            yield ip_service_ooi

            if "cpe" in service:
                for cpe in service["cpe"]:
                    name, version = cpe_to_name_version(cpe=cpe)
                    software_ooi = Software(name=name, version=version, cpe=cpe)
                    yield software_ooi
                    software_instance_ooi = SoftwareInstance(
                        ooi=ip_service_ooi.reference, software=software_ooi.reference
                    )
                    yield software_instance_ooi

                    if module == "malware-simple":
                        malware_ooi = KATFindingType(id="KAT-POTENTIAL-MALWARE")
                        yield malware_ooi
                        yield Finding(
                            finding_type=malware_ooi.reference,
                            ooi=software_ooi.reference,
                            description=f"Software '{cpe}' is known to be used as malware.",
                        )
            else:
                # Less specific than cpe
                if "product" in service:
                    product_name = service["product"]

                    if "version" in service:
                        software_ooi = Software(name=product_name, version=service["version"])
                    else:
                        software_ooi = Software(name=product_name)

                    yield software_ooi
                    software_instance_ooi = SoftwareInstance(
                        ooi=ip_service_ooi.reference, software=software_ooi.reference
                    )
                    yield software_instance_ooi

                    if module == "malware-simple":
                        malware_ooi = KATFindingType(id="KAT-POTENTIAL-MALWARE")
                        yield malware_ooi
                        yield Finding(
                            finding_type=malware_ooi.reference,
                            ooi=software_instance_ooi.reference,
                            description=f"Software '{product_name}' is known to be used as malware.",
                        )

            # (possible) TODO: hostname
