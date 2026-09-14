from bits.definitions import BitDefinition, BitParameterDefinition
from octopoes.models.ooi.software import Software, SoftwareInstance

BIT = BitDefinition(
    id="software-cve",
    consumes=Software,
    parameters=[BitParameterDefinition(ooi_type=SoftwareInstance, relation_path="software")],
    module="bits.software_cve.software_cve",
)
