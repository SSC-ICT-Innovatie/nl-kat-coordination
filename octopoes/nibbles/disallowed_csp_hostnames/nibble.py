from nibbles.definitions import NibbleDefinition, NibbleParameter
from octopoes.models import Reference
from octopoes.models.ooi.config import Config
from octopoes.models.ooi.web import HTTPHeaderHostname


def query(targets: list[Reference | None]) -> str:
    def pull(statements: list[str]) -> str:
        return f"""
            {{
                :query {{
                    :find [(pull ?var [*])] :where [
                        {" ".join(statements)}

                        (or-join [?var ?header]
                            [?var :HTTPHeaderHostname/primary_key ?header]
                            (and
                                [?header :HTTPHeaderHostname/hostname ?hostname]
                                [?hostname :Hostname/network ?network]
                                [?var :Config/ooi ?network]
                                [?var :Config/bit_id "disallowed-csp-hostnames"]
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
                    [?header :HTTPHeaderHostname/primary_key "{str(targets[0])}"]
                """
            ]
        )
    elif sgn == "01":
        return pull(
            [
                f"""
                    [?config :Config/primary_key "{str(targets[1])}"]
                    [?config :Config/ooi ?network]
                    [?hostname :Hostname/network ?network]
                    [?header :HTTPHeaderHostname/hostname ?hostname]
                """
            ]
        )
    elif sgn == "11":
        return f"""
            {{
                :query {{
                    :find [(pull ?var [*])] :where [
                        (or-join [?var]
                            [?var :HTTPHeaderHostname/primary_key "{str(targets[0])}"]
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
                    [?certificate :HTTPHeaderHostname/object_type "HTTPHeaderHostname"]
                """
            ]
        )


NIBBLE = NibbleDefinition(
    id="disallowed_csp_hostnames",
    signature=[
        NibbleParameter(object_type=HTTPHeaderHostname, parser="[*][?object_type == 'HTTPHeaderHostname'][]"),
        NibbleParameter(object_type=Config, parser="[*][?object_type == 'Config'][]", optional=True),
    ],
    query=query,
)
