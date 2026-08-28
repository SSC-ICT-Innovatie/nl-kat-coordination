from nibbles.definitions import NibbleDefinition, NibbleParameter
from octopoes.models import Reference
from octopoes.models.ooi.config import Config
from octopoes.models.ooi.network import Network
from octopoes.models.ooi.web import URL


def query(targets: list[Reference | None]) -> str:
    sgn = "".join(str(int(isinstance(target, Reference))) for target in targets)
    if sgn == "10":
        network = str(Network(name=targets[0].split("|")[1]).reference) if targets[0] is not None else ""
        return f"""
                    {{
                        :query {{
                            :find [(pull ?url [*]) (pull ?config [*])] :where [

                                [?url :object_type "URL"]
                                [?url :URL/primary_key "{str(targets[0])}"]

                                (or
                                    (and
                                        [?config :Config/ooi "{network}"]
                                        [?config :Config/bit_id "superkat"]
                                    )
                                    (and
                                        [(identity nil) ?config]
                                    )
                                )

                            ]
                        }}
                    }}
                """
    elif sgn == "01":
        network = str(Network(name=targets[1].split("|")[1]).reference) if targets[1] is not None else ""
        return f"""
                    {{
                        :query {{
                            :find [(pull ?url [*]) (pull ?config [*])] :where [

                                [?config :object_type "Config"]
                                [?config :Config/primary_key "{str(targets[1])}"]
                                [?config :Config/bit_id "superkat"]

                                (or
                                    (and
                                        [?url :URL/network "{network}"]
                                    )
                                    (and
                                        [(identity nil) ?url]
                                    )
                                )

                            ]
                        }}
                    }}
                """
    elif sgn == "11":
        return f"""
                   {{
                       :query {{
                           :find [(pull ?url [*]) (pull ?config [*])] :where [
                                [?url :object_type "URL"]
                                [?url :URL/primary_key "{str(targets[0])}"]
                                [?config :object_type "Config"]
                                [?config :Config/primary_key "{str(targets[1])}"]
                                [?config :Config/bit_id "superkat"]
                              ]
                         }}
                    }}
                """
    else:
        return """
                   {
                       :query {
                           :find [(pull ?url [*]) (pull ?config [*])] :where [

                                [?url :object_type "URL"]

                                (or
                                    (and
                                        [?url :URL/network ?network]
                                        [?config :Config/ooi ?network]
                                        [?config :object_type "Config"]
                                        [?config :Config/bit_id "superkat"]
                                    )
                                    (and
                                        [(identity nil) ?network]
                                        [(identity nil) ?config]
                                    )
                                )
                              ]
                         }
                    }
               """


NIBBLE = NibbleDefinition(
    id="max_url_length_config",
    signature=[
        NibbleParameter(object_type=URL, parser="[*][?object_type == 'URL'][]"),
        NibbleParameter(object_type=Config, parser="[*][?object_type == 'Config'][]"),
    ],
    query=query,
    enabled=False,
)
