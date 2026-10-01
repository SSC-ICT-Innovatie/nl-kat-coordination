from bits.definitions import BitDefinition, BitParameterDefinition
from octopoes.models.ooi.web import CSPDirective, CSPSource, HTTPHeader, HTTPResource

BIT = BitDefinition(
    id="check-csp-policy",
    consumes=HTTPResource,
    parameters=[
        BitParameterDefinition(ooi_type=HTTPHeader, relation_path="resource"),
        BitParameterDefinition(ooi_type=CSPDirective, relation_path="header.resource"),
        BitParameterDefinition(ooi_type=CSPSource, relation_path="directive.header.resource"),
    ],
    module="bits.check_csp_policy.check_csp_policy",
    config_ooi_relation_path="HTTPResource.website.hostname.network",
)
