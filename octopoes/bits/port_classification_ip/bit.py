from bits.definitions import BitDefinition, BitParameterDefinition
from octopoes.models.ooi.network import IPAddress, IPPort

BIT = BitDefinition(
    id="port-classification-ip",
    consumes=IPAddress,
    parameters=[BitParameterDefinition(ooi_type=IPPort, relation_path="address")],
    module="bits.port_classification_ip.port_classification_ip",
    config_ooi_relation_path="IPAddress.network",
)
