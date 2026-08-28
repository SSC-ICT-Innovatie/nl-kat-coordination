from nibbles.definitions import NibbleDefinition, NibbleParameter
from octopoes.models import Reference
from octopoes.models.ooi.certificate import X509Certificate
from octopoes.models.ooi.config import Config


def query(targets: list[Reference | None]) -> str:
    def pull(statements: list[str]) -> str:
        return f"""
            {{
                :query {{
                    :find [(pull ?var [*])] :where [
                        {" ".join(statements)}

                        (or-join [?var ?certificate]
                            [?var :X509Certificate/primary_key ?certificate]
                            (and
                                [?website :Website/certificate ?certificate]
                                [?website :Website/hostname ?hostname]
                                [?hostname :Hostname/network ?network]
                                [?var :Config/ooi ?network]
                                [?var :Config/bit_id "expiring-certificate"]
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
                    [?certificate :X509Certificate/primary_key "{str(targets[0])}"]
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
                    [?website :Website/hostname ?hostname]
                    [?website :Website/certificate ?certificate]
                """
            ]
        )
    elif sgn == "11":
        return f"""
            {{
                :query {{
                    :find [(pull ?var [*])] :where [
                        (or-join [?var]
                            [?var :X509Certificate/primary_key "{str(targets[0])}"]
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
                    [?certificate :X509Certificate/object_type "X509Certificate"]
                """
            ]
        )


NIBBLE = NibbleDefinition(
    id="expiring-certificate",
    signature=[
        NibbleParameter(object_type=X509Certificate, parser="[*][?object_type == 'X509Certificate'][]"),
        NibbleParameter(object_type=Config, parser="[*][?object_type == 'Config'][]", optional=True),
    ],
    query=query,
)
