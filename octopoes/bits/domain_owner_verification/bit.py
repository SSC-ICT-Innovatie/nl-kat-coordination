from bits.definitions import BitDefinition
from octopoes.models.ooi.dns.records import DNSNSRecord

BIT = BitDefinition(
    id="domain-owner-verification",
    consumes=DNSNSRecord,
    parameters=[],
    module="bits.domain_owner_verification.domain_owner_verification",
)
