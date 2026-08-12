from bits.definitions import BitDefinition
from octopoes.models.ooi.dns.records import DNSTXTRecord

BIT = BitDefinition(
    id="dns-identifiers",
    consumes=DNSTXTRecord,
    parameters=None,
    module="bits.identifiers.identifiers",
    min_scan_level=0,
)
