from bits.definitions import BitDefinition, BitParameterDefinition
from octopoes.models.ooi.network import IPAddress
from octopoes.models.ooi.service import HostnameIPService, IPService

BIT = BitDefinition(
    id="web-service-discovery",
    consumes=IPAddress,
    # The bit instance is keyed on the IP address, like
    # hostname-service-discovery: every IPService and every
    # HostnameIPService on that address arrives as a parameter, and run()
    # derives the Website(s) — including the IP-placeholder Website for
    # web-served endpoints nobody addressed by name.
    parameters=[
        BitParameterDefinition(ooi_type=IPService, relation_path="ip_port.address"),
        BitParameterDefinition(ooi_type=HostnameIPService, relation_path="ip_service.ip_port.address"),
    ],
    module="bits.web_service_discovery.web_service_discovery",
    min_scan_level=0,
)
