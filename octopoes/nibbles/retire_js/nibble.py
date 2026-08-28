from nibbles.definitions import NibbleDefinition, NibbleParameter
from octopoes.models import Reference
from octopoes.models.ooi.software import Software, SoftwareInstance


def query(targets: list[Reference | None]) -> str:
    def pull(statements: list[str]) -> str:
        return f"""
            {{
                :query {{
                    :find [(pull ?software [*])(pull ?instance [*])] :where [
                        [?software :object_type "Software"]
                        [?instance :SoftwareInstance/software ?software]
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
                    [?software :Software/primary_key "{str(targets[0])}"]
                """
            ]
        )

    if sgn == "01":
        return pull(
            [
                f"""
                    [?instance :SoftwareInstance/primary_key "{str(targets[1])}"]
                """
            ]
        )

    if sgn == "11":
        return pull(
            [
                f"""
                    [?software :Software/primary_key "{str(targets[0])}"]
                    [?instance :SoftwareInstance/primary_key "{str(targets[1])}"]
                """
            ]
        )

    else:
        return pull([""])


NIBBLE = NibbleDefinition(
    id="retire-js",
    signature=[
        NibbleParameter(object_type=Software, parser="[*][?object_type == 'Software'][]"),
        NibbleParameter(object_type=SoftwareInstance, parser="[*][?object_type == 'SoftwareInstance'][]"),
    ],
    query=query,
)
