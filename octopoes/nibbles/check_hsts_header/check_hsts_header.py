import datetime
from collections.abc import Iterator

from octopoes.models import OOI, Reference
from octopoes.models.ooi.config import Config
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import HTTPHeader


def nibble(header: HTTPHeader, config: Config | None) -> Iterator[OOI]:
    # TODO: probably this can be done in EDN
    if header.key.lower() != "strict-transport-security":
        return

    one_year = datetime.timedelta(days=365).total_seconds()

    max_age = int(str(config.config.get("max-age", one_year))) if config and config.config else one_year
    findings: list[str] = []

    headervalue = header.value.lower()
    if "includesubdomains" not in headervalue:
        findings.append("The HSTS should include subdomains.")

    if "max-age" not in headervalue:
        findings.append("The cache validity period of the HSTS should be defined and should be at least 1 year.")

    try:
        if "max-age" in headervalue and int(headervalue.split("=")[1].strip('"').split(";")[0]) < max_age:
            findings.append(f"The cache validity period of the HSTS should be at least be {max_age} seconds.")
    except ValueError:
        findings.append("The max-age value should be an integer.")

    if findings:
        description: str = "List of HSTS findings:\n"
        for index, finding in enumerate(findings):
            description += f"\n {index + 1}. {finding}"

        yield from _create_kat_finding(header.reference, kat_id="KAT-HSTS-VULNERABILITIES", description=description)


def _create_kat_finding(header: Reference, kat_id: str, description: str) -> Iterator[OOI]:
    finding_type = KATFindingType(id=kat_id)
    yield finding_type
    yield Finding(finding_type=finding_type.reference, ooi=header, description=description)
