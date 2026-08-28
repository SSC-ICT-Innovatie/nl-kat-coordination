from nibbles.definitions import NibbleDefinition, NibbleParameter
from octopoes.models import Reference
from octopoes.models.ooi.config import Config
from octopoes.models.ooi.web import HTTPHeader


def query(targets: list[Reference | None]) -> str:
    def pull(statements: list[str]) -> str:
        return f"""
            {{
                :query {{
                    :find [(pull ?var [*])] :where [
                        {" ".join(statements)}

                        (or-join [?var ?header]
                            [?var :HTTPHeader/primary_key ?header]
                            (and
                                [?header :HTTPHeader/resource ?resource]
                                [?resource :HTTPResource/web_url ?url]
                                [?url :HostnameHTTPURL/network ?network]
                                [?var :Config/ooi ?network]
                                [?var :Config/bit_id "check-hsts-header"]
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
                    [?header :HTTPHeader/primary_key "{str(targets[0])}"]
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
                    [?url :HostnameHTTPURL/network ?network]
                    [?resource :HTTPResource/web_url ?url]
                    [?header :HTTPHeader/resource ?resource]
                """
            ]
        )
    elif sgn == "11":
        return f"""
            {{
                :query {{
                    :find [(pull ?var [*])] :where [
                        (or-join [?var]
                            [?var :HTTPHeader/primary_key "{str(targets[0])}"]
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
                    [?header :HTTPHeader/object_type "HTTPHeader"]
                """
            ]
        )


NIBBLE = NibbleDefinition(
    id="check-hsts-header",
    signature=[
        NibbleParameter(object_type=HTTPHeader, parser="[*][?object_type == 'HTTPHeader'][]"),
        NibbleParameter(object_type=Config, parser="[*][?object_type == 'Config'][]", optional=True),
    ],
    query=query,
)
