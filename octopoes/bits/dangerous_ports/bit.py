from bits.definitions import BitDefinition
from octopoes.models.ooi.network import IPPort

BIT = BitDefinition(id="dangerous-ports", consumes=IPPort, parameters=[], module="bits.dangerous_ports.dangerous_ports")
