from bits.definitions import BitDefinition, BitParameterDefinition
from octopoes.models.ooi.web import HTTPHeader, HTTPResource

BIT = BitDefinition(
    id="check-csp-header",
    consumes=HTTPResource,
    parameters=[BitParameterDefinition(ooi_type=HTTPHeader, relation_path="resource")],
    module="bits.check_csp_header.check_csp_header",
)
