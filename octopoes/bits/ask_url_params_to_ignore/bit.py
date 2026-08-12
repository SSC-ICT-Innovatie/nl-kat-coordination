from bits.definitions import BitDefinition
from octopoes.models.ooi.network import Network

BIT = BitDefinition(
    id="ask_url_params_to_ignore",
    consumes=Network,
    parameters=[],
    min_scan_level=0,
    module="bits.ask_url_params_to_ignore.ask_url_params_to_ignore",
)
