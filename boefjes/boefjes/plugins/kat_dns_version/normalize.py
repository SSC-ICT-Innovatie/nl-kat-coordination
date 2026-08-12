import json
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.software import Software, SoftwareInstance


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    input_ooi_reference = Reference.from_str(input_ooi["primary_key"])

    results = json.loads(raw)
    for version in results:
        if version.startswith("bind"):
            name = "bind"
            version_number = version.split("-")[1]
        elif version.startswith("9."):
            name = "bind"
            version_number = version
        elif version.startswith("Microsoft DNS"):
            name = "Microsoft DNS"
            version_number = version.replace("Microsoft DNS ", "").split(" ")[0]
        elif version.startswith("dnsmasq"):
            name = "dnsmasq"
            version_number = version.split("-")[1]
        elif version.startswith("PowerDNS"):
            name = "PowerDNS"
            version_number = version.replace("PowerDNS Authoritative Server ", "").split(" ")[0]
        else:
            name = None
            version_number = None

        if name and version_number:
            software = Software(name=name, version=version_number)
            software_instance = SoftwareInstance(ooi=input_ooi_reference, software=software.reference)
            yield from [software, software_instance]
