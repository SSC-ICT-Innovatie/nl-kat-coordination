import json
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.network import IPPort, PortState, Protocol
from octopoes.models.ooi.software import Software, SoftwareInstance


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    results = json.loads(raw)
    ooi = Reference.from_str(input_ooi["primary_key"])

    for port in results["open_ports"]:
        ip_port_ooi = IPPort(address=ooi, protocol=Protocol("tcp"), port=int(port), state=PortState("open"))
        yield ip_port_ooi

        software_ooi = Software(name="DICOM")
        yield software_ooi
        software_instance_ooi = SoftwareInstance(ooi=ip_port_ooi.reference, software=software_ooi.reference)
        yield software_instance_ooi

        kat_ooi = KATFindingType(id="KAT-DICOM-EXPOSED")
        yield kat_ooi
        yield Finding(
            finding_type=kat_ooi.reference,
            ooi=software_instance_ooi.reference,
            description="A DICOM (Digital Imaging and Communications in Medicine) server is exposed to the internet.",
        )
