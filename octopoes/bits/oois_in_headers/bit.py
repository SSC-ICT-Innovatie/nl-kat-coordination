from bits.definitions import BitDefinition
from octopoes.models.ooi.web import HTTPHeader

BIT = BitDefinition(
    id="oois-in-headers",
    consumes=HTTPHeader,
    parameters=[],
    module="bits.oois_in_headers.oois_in_headers",
    config_ooi_relation_path="HTTPHeader.resource.website.hostname.network",
)
