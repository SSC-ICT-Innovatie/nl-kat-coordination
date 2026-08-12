from bits.definitions import BitDefinition
from octopoes.models.ooi.web import HTTPHeader

BIT = BitDefinition(
    id="check_cve_2021_41773",
    consumes=HTTPHeader,
    parameters=[],
    module="bits.check_cve_2021_41773.check_cve_2021_41773",
)
