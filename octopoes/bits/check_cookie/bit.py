from bits.definitions import BitDefinition
from octopoes.models.ooi.web import Cookie

BIT = BitDefinition(
    id="check-cookie", consumes=Cookie, parameters=[], module="bits.check_cookie.check_cookie", min_scan_level=1
)
