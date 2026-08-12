from bits.definitions import BitDefinition, BitParameterDefinition
from octopoes.models.ooi.web import HTTPHeader, HTTPResource

BIT = BitDefinition(
    id="missing-headers",
    consumes=HTTPResource,
    parameters=[BitParameterDefinition(ooi_type=HTTPHeader, relation_path="resource")],
    module="bits.missing_headers.missing_headers",
)
