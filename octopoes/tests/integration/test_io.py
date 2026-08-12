import json
import os
import time
import uuid
from datetime import datetime
from operator import itemgetter

import pytest

from octopoes.api.models import Declaration, Observation
from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models.ooi.network import Network

if os.environ.get("CI") != "1":
    pytest.skip("Needs XTDB multinode container.", allow_module_level=True)


def test_io(octopoes_api_connector: OctopoesAPIConnector, valid_time: datetime):
    network = Network(name="internet")
    octopoes_api_connector.save_declaration(Declaration(ooi=network, valid_time=valid_time))
    time.sleep(2)

    assert octopoes_api_connector.list_objects(types={Network}, valid_time=valid_time).count == 1
    network_object = octopoes_api_connector.list_objects(types={Network}, valid_time=valid_time).items[0]
    assert network_object.name == "internet"
    assert network_object.reference == network.reference

    txops = octopoes_api_connector.export_all()
    transactions = list(map(itemgetter("txOps"), txops))
    data = {
        "object_type": "Network",
        "user_id": None,
        "Network/primary_key": "Network|internet",
        "Network/name": "internet",
        "xt/id": "Network|internet",
    }
    dt = valid_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    target = json.loads(json.dumps(["put", data, dt]))
    assert any([target in tx for tx in transactions])

    res = octopoes_api_connector.import_new(json.dumps(txops))
    assert res == {"detail": len(transactions)}
    time.sleep(2)

    assert octopoes_api_connector.list_objects(types={Network}, valid_time=valid_time).count == 1
    network_object = octopoes_api_connector.list_objects(types={Network}, valid_time=valid_time).items[0]
    assert network_object.name == "internet"
    assert network_object.reference == network.reference

    network_cat = f"""
    [
      {{
        "txId": 101,
        "txTime": "2024-04-01T13:37:00Z",
        "txOps": [
          [
            "put",
            {{
              "object_type": "Network",
              "user_id": null,
              "Network/primary_key": "Network|😸",
              "Network/name": "😸",
              "xt/id": "Network|😸"
            }},
            "{dt}"
          ]
        ]
      }}
    ]
    """

    res = octopoes_api_connector.import_add(network_cat)
    assert res == {"detail": 1}
    time.sleep(3)

    assert len(list(map(itemgetter("txOps"), octopoes_api_connector.export_all()))) > len(transactions)


def test_duplicate_origin_result_filter(octopoes_api_connector: OctopoesAPIConnector, valid_time: datetime):
    network1 = Network(name="1")
    network2 = Network(name="2")
    octopoes_api_connector.save_observation(
        Observation(
            method="normalizer_id",
            source=network1.reference,
            source_method=None,
            task_id=uuid.uuid4(),
            valid_time=valid_time,
            result=[network1, network1, network2, network2],
        )
    )
    origin = octopoes_api_connector.list_origins(task_id={}, valid_time=valid_time)
    assert len(origin) == 1
    assert len(origin[0].result) == 2
    assert origin[0].result[0] == network1.reference
    assert origin[0].result[1] == network2.reference
