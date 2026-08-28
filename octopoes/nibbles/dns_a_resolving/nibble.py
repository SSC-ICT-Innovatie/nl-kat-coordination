from nibbles.definitions import NibbleDefinition, NibbleParameter
from octopoes.models.ooi.dns.records import DNSARecord

NIBBLE = NibbleDefinition(id="dns_a_resolving", signature=[NibbleParameter(object_type=DNSARecord)])
