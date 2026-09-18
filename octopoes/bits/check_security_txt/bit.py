from bits.definitions import BitDefinition
from octopoes.models.ooi.web import SecurityTXT

BIT = BitDefinition(
    id="check-security-txt", consumes=SecurityTXT, parameters=[], module="bits.check_security_txt.check_security_txt"
)
