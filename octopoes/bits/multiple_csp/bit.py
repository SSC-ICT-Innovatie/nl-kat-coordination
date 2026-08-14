from bits.definitions import BitDefinition, BitParameterDefinition
from octopoes.models.ooi.dns.records import DNSTXTRecord
from octopoes.models.ooi.dns.zone import Hostname

BIT = BitDefinition(
    id="multiple-csp",
    consumes=Hostname,
    parameters=[BitParameterDefinition(ooi_type=DNSTXTRecord, relation_path="hostname")],
    module="bits.multiple_csp.multiple_csp",
)
