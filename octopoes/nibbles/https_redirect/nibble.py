from nibbles.definitions import NibbleDefinition, NibbleParameter
from octopoes.models import Reference
from octopoes.models.ooi.web import HostnameHTTPURL, HTTPHeader


def query(targets: list[Reference | None]) -> str:
    def pull(statements: list[str]) -> str:
        return f"""
                {{
                    :query {{
                        :find [
                                (pull ?hostnamehttpurl [*])
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
            [?hostnamehttpurl :object_type "HostnameHTTPURL"]
            [?headers :HTTPHeader/resource ?resource]
            [?resource :HTTPResource/web_url ?hostnamehttpurl]
        """
    ]

    sgn = "".join(str(int(isinstance(target, Reference))) for target in targets)
    ref_query = [""]
    if sgn.startswith("1"):
        ref_query = [f'[?hostnamehttpurl :HostnameHTTPURL/primary_key "{str(targets[0])}"]']
    elif sgn.endswith("1"):
        ref = str(targets[1]).split("|")[7:12]
        ref[0] = "HostnameHTTPURL"
        target_reference = Reference.from_str("|".join(ref))
        ref_query = [f'[?hostnamehttpurl :HostnameHTTPURL/primary_key "{str(target_reference)}"]']
    return pull(ref_query + base_query)


NIBBLE = NibbleDefinition(
    id="https-redirect",
    signature=[
        NibbleParameter(object_type=HostnameHTTPURL, parser="[*][?object_type == 'HostnameHTTPURL'][]"),
        NibbleParameter(
            object_type=list[HTTPHeader], parser="[[*][?object_type == 'HTTPHeader'][]]", additional={HTTPHeader}
        ),
    ],
    query=query,
)
