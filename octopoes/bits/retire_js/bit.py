from bits.definitions import BitDefinition, BitParameterDefinition
from octopoes.models.ooi.software import Software, SoftwareInstance

BIT = BitDefinition(
    id="retire-js",
    consumes=Software,
    parameters=[BitParameterDefinition(ooi_type=SoftwareInstance, relation_path="software")],
    module="bits.retire_js.retire_js",
)
