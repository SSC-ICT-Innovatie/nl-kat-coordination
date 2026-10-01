from bits.definitions import BitDefinition
from octopoes.models.ooi.web import HTTPHeader

BIT = BitDefinition(id="parse-csp", consumes=HTTPHeader, parameters=[], module="bits.parse_csp.parse_csp")
