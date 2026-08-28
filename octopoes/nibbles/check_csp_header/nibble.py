from nibbles.definitions import NibbleDefinition, NibbleParameter
from octopoes.models import Reference
from octopoes.models.ooi.web import HTTPHeader, HTTPResource


def query(targets: list[Reference | None]) -> str:
    def pull(statements: list[str]) -> str:
        return f"""
                {{
                    :query {{
                        :find [
                                (pull ?resource [*])
                                (pull ?headers [*])
                              ]
                        :where [
                            {" ".join(statements)}
                        ]
                    }}
                }}
        """

    base_query = [
        """
            [?resource :object_type "HTTPResource"]
            [?headers :HTTPHeader/resource ?resource]
        """
    ]

    sgn = "".join(str(int(isinstance(target, Reference))) for target in targets)
    ref_query = []
    if sgn.startswith("1"):
        ref_query = [f'[?resource :HTTPResource/primary_key "{str(targets[0])}"]']
    elif sgn.endswith("1"):
        ref = str(targets[1]).split("|")
        ref.pop()
        ref[0] = "HTTPResource"
        target_reference = Reference.from_str("|".join(ref))
        ref_query = [f'[?resource :HTTPResource/primary_key "{str(target_reference)}"]']
    return pull(ref_query + base_query)


NIBBLE = NibbleDefinition(
    # TODO: Merge with "missing-headers" nibble
    id="check-csp-header",
    signature=[
        NibbleParameter(object_type=HTTPResource, parser="[*][?object_type == 'HTTPResource'][]"),
        NibbleParameter(
            object_type=list[HTTPHeader], parser="[[*][?object_type == 'HTTPHeader'][]]", additional={HTTPHeader}
        ),
    ],
    query=query,
)
