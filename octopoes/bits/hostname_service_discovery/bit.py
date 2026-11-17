from bits.definitions import BitDefinition, BitParameterDefinition
from octopoes.models.ooi.dns.zone import ResolvedHostname
from octopoes.models.ooi.network import IPAddress
from octopoes.models.ooi.service import IPService

BIT = BitDefinition(
    id="hostname-service-discovery",
    consumes=IPAddress,
    parameters=[
        BitParameterDefinition(ooi_type=IPService, relation_path="ip_port.address"),
        BitParameterDefinition(ooi_type=ResolvedHostname, relation_path="address"),
    ],
    module="bits.hostname_service_discovery.hostname_service_discovery",
    min_scan_level=0,
)
