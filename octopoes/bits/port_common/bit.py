from bits.definitions import BitDefinition
from octopoes.models.ooi.network import IPPort

BIT = BitDefinition(
    id="port-common", consumes=IPPort, parameters=[], module="bits.port_common.port_common", default_enabled=False
)
