from nibbles.definitions import NibbleDefinition, NibbleParameter
from octopoes.models.ooi.dns.records import DNSAAAARecord

NIBBLE = NibbleDefinition(id="dns_aaaa_resolving", signature=[NibbleParameter(object_type=DNSAAAARecord)])
