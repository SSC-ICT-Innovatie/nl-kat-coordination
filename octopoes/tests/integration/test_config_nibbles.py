import os
import sys
from collections.abc import Iterator
from datetime import datetime
from unittest.mock import Mock

import pytest
from nibbles.definitions import NibbleDefinition, NibbleParameter

from octopoes.core.service import OctopoesService
from octopoes.models import OOI, Reference
from octopoes.models.ooi.config import Config
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.network import Network
from octopoes.models.ooi.web import URL
from octopoes.models.origin import OriginType

if os.environ.get("CI") != "1":
    pytest.skip("Needs XTDB multinode container.", allow_module_level=True)


counter = 0


def config_nibble_payload(url: URL, config: Config | None) -> Iterator[OOI]:
    global counter
    counter += 1
    if config is not None and str(url.raw) in config.config:
        kft = KATFindingType(id="URL in config")
        yield kft
        yield Finding(finding_type=kft.reference, ooi=url.reference, proof=f"{url.reference} in {config.config}")


def config_nibble_query(targets: list[Reference | None]) -> str:
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
                                        [?config :Config/bit_id "config_nibble_test"]
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
                                [?config :Config/bit_id "config_nibble_test"]

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
                                [?config :Config/bit_id "config_nibble_test"]
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
                                        [?config :Config/bit_id "config_nibble_test"]
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


config_nibble = NibbleDefinition(
    id="config_nibble_test",
    signature=[
        NibbleParameter(object_type=URL, parser="[*][?object_type == 'URL'][]"),
        NibbleParameter(object_type=Config, parser="[*][?object_type == 'Config'][]", optional=True),
    ],
    query=config_nibble_query,
)
config_nibble._payload = getattr(sys.modules[__name__], "config_nibble_payload")


def test_inference_without_config(xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime):
    global counter
    counter = 0
    xtdb_octopoes_service.nibbler.nibbles = {"config_nibble_test": config_nibble}

    network = Network(name="internet")
    url = URL(network=network.reference, raw="https://mispo.es/")

    xtdb_octopoes_service.ooi_repository.save(network, valid_time)
    xtdb_octopoes_service.ooi_repository.save(url, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert xtdb_octopoes_service.ooi_repository.list_oois({Finding}, valid_time).count == 0
    assert xtdb_octopoes_service.ooi_repository.list_oois({KATFindingType}, valid_time).count == 0
    assert counter == 1


def test_inference_with_config(xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime):
    global counter
    counter = 0
    xtdb_octopoes_service.nibbler.nibbles = {"config_nibble_test": config_nibble}

    network = Network(name="internet")
    url = URL(network=network.reference, raw="https://mispo.es/")
    config = Config(ooi=network.reference, bit_id="config_nibble_test", config={str(url.raw): None})

    xtdb_octopoes_service.ooi_repository.save(network, valid_time)
    xtdb_octopoes_service.ooi_repository.save(url, valid_time)
    xtdb_octopoes_service.ooi_repository.save(config, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert xtdb_octopoes_service.ooi_repository.list_oois({Finding}, valid_time).count == 1
    assert xtdb_octopoes_service.ooi_repository.list_oois({KATFindingType}, valid_time).count == 1
    assert counter == 2


def test_inference_with_other_config(xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime):
    global counter
    counter = 0
    xtdb_octopoes_service.nibbler.nibbles = {"config_nibble_test": config_nibble}

    network = Network(name="internet")
    network_potato = Network(name="potato")
    url = URL(network=network.reference, raw="https://mispo.es/")
    config = Config(ooi=network_potato.reference, bit_id="config_nibble_test", config={str(url.raw): None})

    xtdb_octopoes_service.ooi_repository.save(network, valid_time)
    xtdb_octopoes_service.ooi_repository.save(network_potato, valid_time)
    xtdb_octopoes_service.ooi_repository.save(url, valid_time)
    xtdb_octopoes_service.ooi_repository.save(config, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert xtdb_octopoes_service.ooi_repository.list_oois({Finding}, valid_time).count == 0
    assert xtdb_octopoes_service.ooi_repository.list_oois({KATFindingType}, valid_time).count == 0
    assert counter == 1


def test_inference_with_fake_id_config(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    global counter
    counter = 0
    xtdb_octopoes_service.nibbler.nibbles = {"config_nibble_test": config_nibble}

    network = Network(name="internet")
    url = URL(network=network.reference, raw="https://mispo.es/")
    config = Config(ooi=network.reference, bit_id="fake_id", config={str(url.raw): None})

    xtdb_octopoes_service.ooi_repository.save(network, valid_time)
    xtdb_octopoes_service.ooi_repository.save(url, valid_time)
    xtdb_octopoes_service.ooi_repository.save(config, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert xtdb_octopoes_service.ooi_repository.list_oois({Finding}, valid_time).count == 0
    assert xtdb_octopoes_service.ooi_repository.list_oois({KATFindingType}, valid_time).count == 0
    assert counter == 1


def test_inference_with_changed_config(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    global counter
    counter = 0
    xtdb_octopoes_service.nibbler.nibbles = {"config_nibble_test": config_nibble}

    network = Network(name="internet")
    url = URL(network=network.reference, raw="https://mispo.es/")
    config = Config(ooi=network.reference, bit_id="config_nibble_test", config={str(url.raw): None})

    xtdb_octopoes_service.ooi_repository.save(network, valid_time)
    xtdb_octopoes_service.ooi_repository.save(url, valid_time)
    xtdb_octopoes_service.ooi_repository.save(config, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert xtdb_octopoes_service.ooi_repository.list_oois({Finding}, valid_time).count == 1
    assert xtdb_octopoes_service.ooi_repository.list_oois({KATFindingType}, valid_time).count == 1
    assert counter == 2

    config = Config(ooi=network.reference, bit_id="config_nibble_test", config={})
    xtdb_octopoes_service.ooi_repository.save(config, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert xtdb_octopoes_service.ooi_repository.list_oois({Finding}, valid_time).count == 0
    assert xtdb_octopoes_service.ooi_repository.list_oois({KATFindingType}, valid_time).count == 0
    assert counter == 3

    assert len(xtdb_octopoes_service.origin_repository.list_origins(valid_time, origin_type=OriginType.NIBBLET)) == 1


def test_retrieve(xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime):
    xtdb_octopoes_service.nibbler.nibbles = {"config_nibble_test": config_nibble}

    network = Network(name="internet")
    url = URL(network=network.reference, raw="https://mispo.es/")
    config = Config(ooi=network.reference, bit_id="config_nibble_test", config={str(url.raw): None})

    xtdb_octopoes_service.ooi_repository.save(network, valid_time)
    xtdb_octopoes_service.ooi_repository.save(url, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    xtdb_url = xtdb_octopoes_service.ooi_repository.get(url.reference, valid_time)

    retrieved = xtdb_octopoes_service.nibbler.retrieve(["config_nibble_test"], valid_time)
    assert len(retrieved) == 1
    assert retrieved["config_nibble_test"][0] == [xtdb_url, None]

    xtdb_octopoes_service.ooi_repository.save(config, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    xtdb_config = xtdb_octopoes_service.ooi_repository.get(config.reference, valid_time)

    retrieved = xtdb_octopoes_service.nibbler.retrieve(["config_nibble_test"], valid_time)
    assert len(retrieved) == 1
    assert retrieved["config_nibble_test"][0] == [xtdb_url, xtdb_config]


def test_nibble_origin_deletion_propagation_with_optional(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    global counter
    counter = 0
    xtdb_octopoes_service.nibbler.nibbles = {"config_nibble_test": config_nibble}

    network = Network(name="internet")
    url = URL(network=network.reference, raw="https://mispo.es/")
    config = Config(ooi=network.reference, bit_id="config_nibble_test", config={str(url.raw): None})

    xtdb_octopoes_service.ooi_repository.save(network, valid_time)
    xtdb_octopoes_service.ooi_repository.save(url, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)
    assert xtdb_octopoes_service.ooi_repository.list_oois({Finding}, valid_time).count == 0
    assert xtdb_octopoes_service.ooi_repository.list_oois({KATFindingType}, valid_time).count == 0
    assert counter == 1

    xtdb_octopoes_service.ooi_repository.save(config, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)
    assert xtdb_octopoes_service.ooi_repository.list_oois({Finding}, valid_time).count == 1
    assert xtdb_octopoes_service.ooi_repository.list_oois({KATFindingType}, valid_time).count == 1
    assert counter == 2

    xtdb_octopoes_service.ooi_repository.delete(config.reference, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert xtdb_octopoes_service.ooi_repository.list_oois({Finding}, valid_time).count == 0
    assert xtdb_octopoes_service.ooi_repository.list_oois({KATFindingType}, valid_time).count == 0
    assert counter == 4

    xtdb_octopoes_service.ooi_repository.delete(url.reference, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    xtdb_octopoes_service.ooi_repository.save(url, valid_time)
    xtdb_octopoes_service.ooi_repository.save(config, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert xtdb_octopoes_service.ooi_repository.list_oois({Finding}, valid_time).count == 1
    assert xtdb_octopoes_service.ooi_repository.list_oois({KATFindingType}, valid_time).count == 1
    assert counter == 6
