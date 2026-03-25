import json
import logging
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import CVEFindingType, Finding
from octopoes.models.ooi.network import IPPort, PortState, Protocol


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    results = json.loads(raw)
    ooi = Reference.from_str(input_ooi["primary_key"])

    if not results:
        logging.info("No Shodan results available for normalization.")
    elif "data" not in results:
        logging.warning("Shodan results exist without data.")
    else:
        for scan in results["data"]:
            port_nr = scan["port"]
            transport = scan["transport"]

            ip_port = IPPort(address=ooi, protocol=Protocol(transport), port=int(port_nr), state=PortState("open"))
            yield ip_port

            if "vulns" in scan:
                for cve in scan["vulns"].values():
                    ft = CVEFindingType(id=cve)
                    f = Finding(finding_type=ft.reference, ooi=ip_port.reference)
                    yield ft
                    yield f
