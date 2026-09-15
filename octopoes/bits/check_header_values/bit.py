from bits.definitions import BitDefinition, BitParameterDefinition
from octopoes.models.ooi.web import HTTPHeader, HTTPResource

BIT = BitDefinition(
    id="check-header-values",
    consumes=HTTPResource,
    parameters=[BitParameterDefinition(ooi_type=HTTPHeader, relation_path="resource")],
    module="bits.check_header_values.check_header_values",
)
