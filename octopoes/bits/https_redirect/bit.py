from bits.definitions import BitDefinition, BitParameterDefinition
from octopoes.models.ooi.web import HostnameHTTPURL, HTTPHeader

BIT = BitDefinition(
    id="https-redirect",
    consumes=HostnameHTTPURL,
    parameters=[BitParameterDefinition(ooi_type=HTTPHeader, relation_path="resource.web_url")],
    module="bits.https_redirect.https_redirect",
)
