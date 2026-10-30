from bits.definitions import BitDefinition
from octopoes.models.ooi.dns.records import DNSCAARecord

BIT = BitDefinition(
    id="dns-caa-parsing",
    consumes=DNSCAARecord,
    parameters=[],
    module="bits.dns_caa_parsing.dns_caa_parsing",
    min_scan_level=0,
)
