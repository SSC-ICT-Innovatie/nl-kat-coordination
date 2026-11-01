from bits.definitions import BitDefinition, BitParameterDefinition
from octopoes.models.ooi.dns.records import DNSTXTRecord
from octopoes.models.ooi.dns.zone import Hostname

BIT = BitDefinition(
    id="multiple-spf",
    consumes=Hostname,
    parameters=[BitParameterDefinition(ooi_type=DNSTXTRecord, relation_path="hostname")],
    module="bits.multiple_spf.multiple_spf",
)
