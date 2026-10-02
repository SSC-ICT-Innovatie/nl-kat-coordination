from bits.definitions import BitDefinition, BitParameterDefinition
from octopoes.models.ooi.dns.records import NXDOMAIN, DNSMXRecord
from octopoes.models.ooi.dns.zone import Hostname

BIT = BitDefinition(
    id="missing-mx",
    consumes=Hostname,
    parameters=[
        BitParameterDefinition(ooi_type=DNSMXRecord, relation_path="hostname"),
        BitParameterDefinition(ooi_type=NXDOMAIN, relation_path="hostname"),
    ],
    module="bits.missing_mx.missing_mx",
)
