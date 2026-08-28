from nibbles.definitions import NibbleDefinition, NibbleParameter
from octopoes.models import Reference
from octopoes.models.ooi.dns.records import NXDOMAIN
from octopoes.models.ooi.web import HTTPHeaderHostname


def query(targets: list[Reference | None]) -> str:
    def pull(statements: list[str]) -> str:
        return f"""
            {{
                :query {{
                    :find [(pull ?httpheaderhostname [*])(pull ?nxdomain [*])] :where [
                        {" ".join(statements)}
                        [?httpheaderhostname :HTTPHeaderHostname/hostname ?hostname]
                        [?nxdomain :NXDOMAIN/hostname ?hostname]
                    ]
                }}
            }}
        """

    sgn = "".join(str(int(isinstance(target, Reference))) for target in targets)

    if sgn == "10":
        return pull(
            [
                f"""
                    [?httpheaderhostname :HTTPHeaderHostname/primary_key "{str(targets[0])}"]
                """
            ]
        )

    elif sgn == "01":
        return pull(
            [
                f"""
                    [?nxdomain :NXDOMAIN/primary_key "{str(targets[1])}"]
                """
            ]
        )

    elif sgn == "11":
        return pull(
            [
                f"""
                    [?httpheaderhostname :HTTPHeaderHostname/primary_key "{str(targets[0])}"]
                    [?nxdomain :NXDOMAIN/primary_key "{str(targets[1])}"]
                """
            ]
        )

    else:
        return pull([""])


NIBBLE = NibbleDefinition(
    id="nxdomain_header_flag",
    signature=[
        NibbleParameter(object_type=HTTPHeaderHostname, parser="[*][?object_type == 'HTTPHeaderHostname'][]"),
        NibbleParameter(object_type=NXDOMAIN, parser="[*][?object_type == 'NXDOMAIN'][]"),
    ],
    query=query,
)
