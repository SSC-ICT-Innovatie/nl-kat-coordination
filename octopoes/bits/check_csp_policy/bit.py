from bits.definitions import BitDefinition, BitParameterDefinition
from octopoes.models.ooi.web import CSPDirective, CSPSource, HTTPHeader

BIT = BitDefinition(
    id="check-csp-policy",
    consumes=HTTPHeader,
    parameters=[
        BitParameterDefinition(ooi_type=CSPDirective, relation_path="header"),
        BitParameterDefinition(ooi_type=CSPSource, relation_path="directive.header"),
    ],
    module="bits.check_csp_policy.check_csp_policy",
    config_ooi_relation_path="HTTPHeader.resource.website.hostname.network",
)
