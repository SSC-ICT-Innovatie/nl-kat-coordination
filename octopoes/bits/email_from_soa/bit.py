from bits.definitions import BitDefinition
from octopoes.models.ooi.dns.records import DNSSOARecord

BIT = BitDefinition(
    id="email-from-soa",
    consumes=DNSSOARecord,
    parameters=[],
    module="bits.email_from_soa.email_from_soa",
    min_scan_level=0,
)
