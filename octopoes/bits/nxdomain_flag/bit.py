from bits.definitions import BitDefinition, BitParameterDefinition
from octopoes.models.ooi.dns.records import NXDOMAIN
from octopoes.models.ooi.dns.zone import Hostname

BIT = BitDefinition(
    id="nxdomain-flag",
    consumes=Hostname,
    parameters=[BitParameterDefinition(ooi_type=NXDOMAIN, relation_path="hostname")],
    module="bits.nxdomain_flag.nxdomain_flag",
)
