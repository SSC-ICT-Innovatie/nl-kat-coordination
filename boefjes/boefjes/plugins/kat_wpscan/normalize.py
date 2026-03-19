import json
from collections.abc import Iterable

from wpscan_out_parse import WPScanJsonParser

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import CVEFindingType, Finding


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    url_reference = Reference.from_str(input_ooi["primary_key"])

    if raw:
        data = json.loads(raw.decode())
        results = WPScanJsonParser(data)
        for alert in results.get_alerts():
            lines = alert.splitlines()
            for line in lines:
                if "CVE: " in line:
                    cve = line.split("=")
                    id_ = cve[-1]
                    if "CVE-" in id_:
                        ft = CVEFindingType(id=id_)
                        yield ft
                        finding = Finding(
                            finding_type=ft.reference, ooi=url_reference, description=alert.splitlines()[0]
                        )
                        yield finding
