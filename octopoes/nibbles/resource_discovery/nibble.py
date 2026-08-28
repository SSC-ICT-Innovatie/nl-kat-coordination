from nibbles.definitions import NibbleDefinition, NibbleParameter
from octopoes.models import Reference
from octopoes.models.ooi.web import HostnameHTTPURL, Website


def query(targets: list[Reference | None]) -> str:
    def pull(statements: list[str]) -> str:
        return f"""
            {{
                :query {{
                    :find [(pull ?hostname_http_url [*])(pull ?website [*])] :where [
                        [?hostname_http_url :HostnameHTTPURL/netloc ?hostname]
                        [?website :Website/hostname ?hostname]
                        [?website :Website/ip_service ?ip_service]
                        [?ip_service :IPService/ip_port ?ip_port]
                        [?ip_port :IPPort/port ?port]
                        [?hostname_http_url :HostnameHTTPURL/port ?port]
                        [?ip_service :IPService/service ?service]
                        [?service :Service/name ?name]
                        [?hostname_http_url :HostnameHTTPURL/scheme ?name]
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
                    [?hostname_http_url :HostnameHTTPURL/primary_key "{str(targets[0])}"]
                """
            ]
        )

    if sgn == "01":
        return pull(
            [
                f"""
                    [?website :Website/primary_key "{str(targets[1])}"]
                """
            ]
        )

    if sgn == "11":
        return pull(
            [
                f"""
                    [?hostname_http_url :HostnameHTTPURL/primary_key "{str(targets[0])}"]
                    [?website :Website/primary_key "{str(targets[1])}"]
                """
            ]
        )

    else:
        return pull([""])


NIBBLE = NibbleDefinition(
    id="resource_discovery",
    signature=[
        NibbleParameter(object_type=HostnameHTTPURL, parser="[*][?object_type == 'HostnameHTTPURL'][]"),
        NibbleParameter(object_type=Website, parser="[*][?object_type == 'Website'][]"),
    ],
    query=query,
)
