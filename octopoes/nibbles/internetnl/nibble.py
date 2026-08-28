from nibbles.definitions import NibbleDefinition, NibbleParameter
from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname, Network
from octopoes.models.ooi.findings import Finding

FINDING_TYPES = [
    "KAT-WEBSERVER-NO-IPV6",
    "KAT-NAMESERVER-NO-TWO-IPV6",
    "KAT-NO-DNSSEC",
    "KAT-INVALID-DNSSEC",
    "KAT-NO-HSTS",
    "KAT-NO-CSP",
    "KAT-NO-X-FRAME-OPTIONS",
    "KAT-NO-X-CONTENT-TYPE-OPTIONS",
    "KAT-CSP-VULNERABILITIES",
    "KAT-HSTS-VULNERABILITIES",
    "KAT-NO-CERTIFICATE",
    "KAT-HTTPS-NOT-AVAILABLE",
    "KAT-SSL-CERT-HOSTNAME-MISMATCH",
    "KAT-HTTPS-REDIRECT",
]


def or_finding_types() -> str:
    clauses = "".join([f'[?finding :Finding/finding_type "KATFindingType|{ft}"]' for ft in FINDING_TYPES])
    return f"(or {clauses})"


def query(targets: list[Reference | None]) -> str:
    def pull(statements: list[str]) -> str:
        return f"""
                {{
                    :query {{
                        :find [
                                (pull ?hostname [*])
                                (pull ?website [*])
                                (pull ?finding [*])
                              ]
                        :where [
                            {" ".join(statements)}
                        ]
                    }}
                }}
        """

    base_query = [
        """
            [?hostname :object_type "Hostname"]
            [?website :Website/hostname ?hostname]
            (or-join [?finding ?hostname ?website]
                [?finding :Finding/ooi ?hostname]
                (and
                    [?hostnamehttpurl :HostnameHTTPURL/netloc ?hostname]
                    [?finding :Finding/ooi ?hostnamehttpurl]
                )
                [?finding :Finding/ooi ?website]
                (and
                    [?resource :HTTPResource/website ?website]
                    [?finding :Finding/ooi ?resource]
                )
                (and
                    [?header :HTTPHeader/resource ?resource]
                    [?resource :HTTPResource/website ?website]
                    [?finding :Finding/ooi ?header]
                )
            )
        """
    ]

    null_query = '{:query {:find [(pull ?var [])] :where [[?var :null ""][?var :null "NULL"]]}}'
    sgn = "".join(str(int(isinstance(target, Reference))) for target in targets)
    ref_query = []
    if sgn.startswith("1"):
        ref_query = [f'[?hostname :Hostname/primary_key "{str(targets[0])}"]']
    elif sgn.endswith("1"):
        ref = str(targets[1]).split("|")
        tokens = ref[1:-1]
        target_reference = Reference.from_str("|".join(tokens))
        if tokens[0] == "Hostname":
            hostname = target_reference.tokenized
        elif tokens[0] in {"HostnameHTTPURL", "Website"}:
            hostname = target_reference.tokenized.hostname
        elif tokens[0] == "HTTPResource":
            hostname = target_reference.tokenized.website.hostname
        elif tokens[0] == "HTTPHeader":
            hostname = target_reference.tokenized.resource.website.hostname
        else:
            return null_query
        hostname_pk = Hostname(name=hostname.name, network=Network(name=hostname.network.name).reference).reference
        ref_query = [f'[?hostname :Hostname/primary_key "{str(hostname_pk)}"]']
    return pull(ref_query + [or_finding_types()] + base_query)


NIBBLE = NibbleDefinition(
    id="internet_nl",
    signature=[
        NibbleParameter(object_type=Hostname, parser="[*][?object_type == 'Hostname'][]"),
        NibbleParameter(object_type=list[Finding], parser="[[*][?object_type == 'Finding'][]]", additional={Finding}),
    ],
    query=query,
    enabled=False,
)
