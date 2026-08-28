from nibbles.definitions import NibbleDefinition, NibbleParameter
from octopoes.models import Reference
from octopoes.models.ooi.config import Config
from octopoes.models.ooi.network import IPPort


def query(targets: list[Reference | None]) -> str:
    def pull(statements: list[str]) -> str:
        return f"""
            {{
                :query {{
                    :find [(pull ?var [*])] :where [
                        {" ".join(statements)}
                        (or-join [?var ?ip_port]
                            [?var :IPPort/primary_key ?ip_port]
                            (and
                                [?ip_port :IPPort/address ?ip_address]
                                [?ip_address :IPAddress/network ?network]
                                [?var :Config/ooi ?network]
                                [?var :Config/bit_id "port-classification-ip"]
                            )
                        )
                    ]
                }}
            }}
        """

    sgn = "".join(str(int(isinstance(target, Reference))) for target in targets)
    if sgn == "10":
        return pull(
            [
                f"""
                    [?header :IPPort/primary_key "{str(targets[0])}"]
                """
            ]
        )
    elif sgn == "01":
        return pull(
            [
                f"""
                    [?config :Config/primary_key "{str(targets[1])}"]
                    [?config :Config/ooi ?network]
                    [?ip_port :IPPort/address ?ip_address]
                    [?ip_address :IPAddress/network ?network]
                """
            ]
        )
    elif sgn == "11":
        return f"""
            {{
                :query {{
                    :find [(pull ?var [*])] :where [
                        (or-join [?var]
                            [?var :IPPort/primary_key "{str(targets[0])}"]
                            [?var :Config/primary_key "{str(targets[1])}"]
                        )
                    ]
                 }}
            }}
        """
    else:
        return pull(
            [
                """
                    [?ip_address :IPPort/object_type "IPPort"]
                """
            ]
        )


NIBBLE = NibbleDefinition(
    id="port-classification-ip",
    signature=[
        NibbleParameter(object_type=IPPort, parser="[*][?object_type == 'IPPort'][]"),
        NibbleParameter(object_type=Config, parser="[*][?object_type == 'Config'][]", optional=True),
    ],
    query=query,
)
