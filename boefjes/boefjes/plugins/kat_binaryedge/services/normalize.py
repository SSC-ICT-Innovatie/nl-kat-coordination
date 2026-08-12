import ipaddress
import json
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from boefjes.plugins.helpers import cpe_to_name_version
from octopoes.models import Reference
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, IPPort, Network, PortState, Protocol
from octopoes.models.ooi.software import Software, SoftwareInstance


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    results = json.loads(raw)
    pk_ooi = Reference.from_str(input_ooi["primary_key"])
    network = Network(name="internet").reference

    # Structure based on https://docs.binaryedge.io/modules/<accepted_modules_name>/
    accepted_modules = ("ssh", "rsync", "ftp", "telnet", "smb")
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

        if module == "ssh":
            version_ssh = scan.get("result", {}).get("data", {}).get("banner")
            if version_ssh:
                software_ooi = Software(name=module.upper(), version=version_ssh)
            else:
                software_ooi = Software(name=module.upper())
            yield software_ooi
            yield SoftwareInstance(ooi=ip_port_ooi.reference, software=software_ooi.reference)
        elif module == "rsync":
            software_ooi = Software(name=module.upper(), version=scan.get("result", {}).get("data", {}).get("version"))
            yield software_ooi
            yield SoftwareInstance(ooi=ip_port_ooi.reference, software=software_ooi.reference)
        elif module == "telnet":
            software_ooi = Software(name=module.upper())
            yield software_ooi
            yield SoftwareInstance(ooi=ip_port_ooi.reference, software=software_ooi.reference)
        elif module == "smb":
            for dialect in scan.get("result", {}).get("data", {}).get("smb_dialects", []):
                software_ooi = Software(name=module.upper(), version=dialect)
                yield software_ooi
                yield SoftwareInstance(ooi=ip_port_ooi.reference, software=software_ooi.reference)
            for cpe in scan.get("result", {}).get("data", {}).get("cpe", []):
                name, version = cpe_to_name_version(cpe=cpe)
                software_ooi = Software(name=name, version=version, cpe=cpe)
                yield software_ooi
                yield SoftwareInstance(ooi=ip_port_ooi.reference, software=software_ooi.reference)

        # (potential) TODO: SSH: hassh, hassh-algoritms
        # (potential) TODO: RSYNC: result.data.status
        # (potential) TODO: RSYNC: result.data.modules[].status
