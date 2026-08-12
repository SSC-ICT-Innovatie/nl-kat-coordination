from collections.abc import Iterator

from octopoes.models import OOI
from octopoes.models.ooi.dns.records import DNSNSRecord
from octopoes.models.ooi.findings import Finding, KATFindingType

INDICATORS = [
    "NS1.REGISTRANT-VERIFICATION.ISPAPI.NET",
    "NS2.REGISTRANT-VERIFICATION.ISPAPI.NET",
    "NS3.REGISTRANT-VERIFICATION.ISPAPI.NET",
]


def run(nameserver_record: DNSNSRecord, additional_oois, config: dict[str, str]) -> Iterator[OOI]:
    """Checks to see if a domain has a specific set of dns servers which would indicate domain registrant verification.
    https://support.dnsimple.com/articles/icann-domain-validation/
    """
    if nameserver_record.name_server_hostname.tokenized.name.rstrip(".").upper() in INDICATORS:
        finding_type = KATFindingType(id="KAT-DOMAIN-OWNERSHIP-PENDING")
        yield finding_type
        yield Finding(
            finding_type=finding_type.reference,
            ooi=nameserver_record.hostname,
            description="This domain requires ownership verification and is currently pending.",
        )
