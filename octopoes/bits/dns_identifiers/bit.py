from bits.definitions import BitDefinition
from octopoes.models.ooi.dns.records import DNSTXTRecord

BIT = BitDefinition(
    id="dns-identifiers",
    consumes=DNSTXTRecord,
    parameters=[],
    module="bits.dns_identifiers.dns_identifiers",
    min_scan_level=1,
)
