from bits.definitions import BitDefinition
from octopoes.models.ooi.dns.records import DNSTXTRecord

BIT = BitDefinition(id="spf-discovery", consumes=DNSTXTRecord, parameters=[], module="bits.spf_discovery.spf_discovery")
