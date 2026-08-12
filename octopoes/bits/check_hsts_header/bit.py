from bits.definitions import BitDefinition
from octopoes.models.ooi.web import HTTPHeader

BIT = BitDefinition(
    id="check-hsts-header",
    consumes=HTTPHeader,
    parameters=[],
    module="bits.check_hsts_header.check_hsts_header",
    config_ooi_relation_path="HTTPHeader.resource.website.hostname.network",
)
