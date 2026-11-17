from bits.definitions import BitDefinition, BitParameterDefinition
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import Finding
from octopoes.models.ooi.web import Website

BIT = BitDefinition(
    id="internet-nl",
    consumes=Hostname,
    parameters=[
        BitParameterDefinition(ooi_type=Finding, relation_path="ooi [is Hostname]"),  # findings on hostnames
        BitParameterDefinition(
            ooi_type=Finding, relation_path="ooi [is HTTPResource].website.hostname"
        ),  # findings on resources
        BitParameterDefinition(
            ooi_type=Finding, relation_path="ooi [is HTTPHeader].resource.website.hostname"
        ),  # findings on headers
        BitParameterDefinition(ooi_type=Finding, relation_path="ooi [is Website].hostname"),  # findings on websites
        BitParameterDefinition(
            ooi_type=Finding, relation_path="ooi [is HostnameHTTPURL].netloc"
        ),  # findings on weburls
        BitParameterDefinition(
            ooi_type=Finding, relation_path="ooi [is IPAddress].<address [is ResolvedHostname].hostname"
        ),
        BitParameterDefinition(
            # chain-bound findings (hostname mismatch) on services named by
            # this hostname
            ooi_type=Finding,
            relation_path="ooi [is TLSCertificateChain].hostname_ip_service.hostname",
        ),
        BitParameterDefinition(ooi_type=Website, relation_path="hostname"),  # only websites have to comply
    ],
    module="bits.internetnl.internetnl",
)
