from nibbles.definitions import NibbleDefinition, NibbleParameter
from octopoes.models.ooi.dns.records import NXDOMAIN

NIBBLE = NibbleDefinition(id="nxdomain_flag", signature=[NibbleParameter(object_type=NXDOMAIN)])
