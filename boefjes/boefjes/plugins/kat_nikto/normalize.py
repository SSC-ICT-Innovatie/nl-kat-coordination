import json
from collections.abc import Iterable
from typing import Any

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.software import Software, SoftwareInstance

MISSING_HEADER_TO_KAT_FINDING_TYPE = {
    "strict-transport-security": "KAT-HSTS-VULNERABILITIES",
    "x-content-type-options": "KAT-NO-X-CONTENT-TYPE-OPTIONS",
    "content-security-policy": "KAT-CSP-VULNERABILITIES",
    "referrer-policy": "KAT-NO-REFERRER-POLICY",
    "permissions-policy": "KAT-NO-PERMISSIONS-POLICY",
}


def scan_nikto_output(data: list[dict[str, Any]], ooi_ref: Reference) -> Iterable[NormalizerOutput]:
    for scan in data:
        for vulnerability in scan["vulnerabilities"]:
            vulnerability_id: str = vulnerability["id"]

            # If the scanned vulnerability has to do with outdated software
            if vulnerability_id.startswith("6"):
                # Example of `vulnerability["msg"]`
                # @SOFTWARE/@RUNNING_VER appears to be outdated (current is at least @CURRENT_VER)
                software_name, found_version = vulnerability["msg"].split()[0].split("/")

                software = Software(name=software_name, version=found_version)
                software_instance = SoftwareInstance(ooi=ooi_ref, software=software.reference)
                yield software
                yield software_instance

                finding_type = KATFindingType(id="KAT-OUTDATED-SOFTWARE")
                yield finding_type
                yield Finding(
                    finding_type=finding_type.reference,
                    ooi=software_instance.reference,
                    description=vulnerability["msg"],
                )

            # If the scanned vulnerability has to do with security headers missing
            elif vulnerability_id == "013587":
                missing_header = vulnerability["msg"].split()[-1].strip(".")

                kat_finding_type_id = MISSING_HEADER_TO_KAT_FINDING_TYPE.get(missing_header)
                if kat_finding_type_id is None:
                    kat_finding_type_id = "KAT-MISSING-HEADER"
                finding_type = KATFindingType(id=kat_finding_type_id)
                yield finding_type
                yield Finding(finding_type=finding_type.reference, ooi=ooi_ref, description=vulnerability["msg"])
            # if the site uses TLS and the Strict-Transport-Security HTTP header is not defined
            elif vulnerability_id == "999970":
                finding_type = KATFindingType(id="KAT-HSTS-VULNERABILITIES")
                yield Finding(finding_type=finding_type.reference, ooi=ooi_ref, description=vulnerability["msg"])


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    data = json.loads(raw)

    ooi_ref = Reference.from_str(input_ooi["primary_key"])

    yield from scan_nikto_output(data, ooi_ref)
