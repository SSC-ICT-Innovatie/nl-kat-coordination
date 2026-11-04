from bits.definitions import BitDefinition, BitParameterDefinition
from octopoes.models.ooi.network import IPAddress, IPPort

BIT = BitDefinition(
    id="https-availability",
    consumes=IPAddress,
    parameters=[BitParameterDefinition(ooi_type=IPPort, relation_path="address")],
    module="bits.https_availability.https_availability",
)
