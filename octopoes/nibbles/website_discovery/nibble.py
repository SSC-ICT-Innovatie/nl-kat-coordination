from nibbles.definitions import NibbleDefinition, NibbleParameter
from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import ResolvedHostname
from octopoes.models.ooi.service import IPService


def query(targets: list[Reference | None]) -> str:
    def pull(statements: list[str]) -> str:
        return f"""
            {{
                :query {{
                    :find [(pull ?resolved_hostname [*])(pull ?ip_service [*])] :where [
                        [?resolved_hostname :ResolvedHostname/address ?ip_address]
                        [?ip_service :IPService/ip_port ?ip_port]
                        [?ip_service :IPService/service ?service]
                        (or-join [?service] [?service :Service/name "http"][?service :Service/name "https"])
                        [?ip_port :IPPort/address ?ip_address]
                        {" ".join(statements)}
                    ]
                }}
            }}
        """

    sgn = "".join(str(int(isinstance(target, Reference))) for target in targets)

    if sgn == "10":
        return pull(
            [
                f"""
                    [?resolved_hostname :ResolvedHostname/primary_key "{str(targets[0])}"]
                """
            ]
        )

    if sgn == "01":
        return pull(
            [
                f"""
                    [?ip_service :IPService/primary_key "{str(targets[1])}"]
                """
            ]
        )

    if sgn == "11":
        return pull(
            [
                f"""
                    [?resolved_hostname :ResolvedHostname/primary_key "{str(targets[0])}"]
                    [?ip_service :IPService/primary_key "{str(targets[1])}"]
                """
            ]
        )

    else:
        return pull([""])


NIBBLE = NibbleDefinition(
    id="website_discovery",
    signature=[
        NibbleParameter(object_type=ResolvedHostname, parser="[*][?object_type == 'ResolvedHostname'][]"),
        NibbleParameter(object_type=IPService, parser="[*][?object_type == 'IPService'][]"),
    ],
    query=query,
)
