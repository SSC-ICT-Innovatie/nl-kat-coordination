from nibbles.definitions import NibbleDefinition, NibbleParameter
from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import ResolvedHostname
from octopoes.models.ooi.network import IPPort


def query(targets: list[Reference | None]) -> str:
    def pull(statements: list[str]) -> str:
        return f"""
            {{
                :query {{
                    :find [(pull ?ip_port [*])(pull ?resolved_hostname [*])] :where [
                        [?ip_port :IPPort/address ?ip_address]
                        (or-join [?ip_port] [?ip_port :IPPort/port 443][?ip_port :IPPort/port 80])
                        [?resolved_hostname :ResolvedHostname/address ?ip_address]
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
                    [?ip_port :IPPort/primary_key "{str(targets[0])}"]
                """
            ]
        )

    if sgn == "01":
        return pull(
            [
                f"""
                    [?resolved_hostname :ResolvedHostname/primary_key "{str(targets[1])}"]
                """
            ]
        )

    if sgn == "11":
        return pull(
            [
                f"""
                    [?ip_port :IPPort/primary_key "{str(targets[0])}"]
                    [?resolved_hostname :ResolvedHostname/primary_key "{str(targets[1])}"]
                """
            ]
        )

    else:
        return pull([""])


NIBBLE = NibbleDefinition(
    id="url-discovery",
    signature=[
        NibbleParameter(object_type=IPPort, parser="[*][?object_type == 'IPPort'][]"),
        NibbleParameter(
            object_type=ResolvedHostname, parser="[*][?object_type == 'ResolvedHostname'][]", optional=True
        ),
    ],
    query=query,
)
