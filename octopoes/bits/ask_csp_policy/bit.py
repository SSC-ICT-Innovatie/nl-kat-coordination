from bits.definitions import BitDefinition
from octopoes.models.ooi.network import Network

BIT = BitDefinition(
    id="ask-csp-policy", consumes=Network, parameters=[], min_scan_level=0, module="bits.ask_csp_policy.ask_csp_policy"
)
