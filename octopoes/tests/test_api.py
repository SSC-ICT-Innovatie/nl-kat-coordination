import logging
import re

import httpx
import pytest
from fastapi.testclient import TestClient

from octopoes.api.api import app
from octopoes.version import __version__

client = TestClient(app)


@pytest.fixture
def patch_pika(mocker):
    return mocker.patch("pika.BlockingConnection")


def test_health(httpx_mock, patch_pika):
    xtdb_status = {
        "version": "1.24.1",
        "revision": "1164f9a3c7e36edbc026867945765fd4366c1731",
        "indexVersion": 22,
        "consumerState": None,
        "kvStore": "xtdb.rocksdb.RocksKv",
        "estimateNumKeys": 525037,
        "size": 35488019,
    }

    httpx_mock.add_response(method="GET", url="http://xtdb:3000/_xtdb/_dev/status", json=xtdb_status, status_code=200)
    response = client.get("/_dev/health")
    assert response.json() == {
        "service": "octopoes",
        "healthy": True,
        "version": __version__,
        "additional": None,
        "results": [
            {"healthy": True, "service": "xtdb", "version": "1.24.1", "additional": xtdb_status, "results": []}
        ],
    }
    assert response.status_code == 200


def test_health_no_xtdb_connection(httpx_mock, patch_pika):
    httpx_mock.add_exception(
        httpx.ConnectTimeout("Connection timed out"), method="GET", url="http://xtdb:3000/_xtdb/_dev/status"
    )
    response = client.get("/_dev/health")
    assert response.json() == {
        "service": "octopoes",
        "healthy": False,
        "version": __version__,
        "additional": None,
        "results": [
            {
                "healthy": False,
                "service": "xtdb",
                "version": None,
                "additional": "Cannot connect to XTDB at. Service possibly down",
                "results": [],
            }
        ],
    }
    assert response.status_code == 200


def test_openapi():
    response = client.get("/openapi.json")
    assert response.status_code == 200


def test_get_scan_profiles(httpx_mock, patch_pika, valid_time):
    scan_profile = {
        "type": "ScanProfile",
        "level": 0,
        "reference": "Hostname|internet|mispo.es",
        "scan_profile_type": "empty",
        "xt/id": "ScanProfile|DNSZone|internet|mispo.es",
    }

    httpx_mock.add_response(
        method="POST",
        url=re.compile(r"http://xtdb:3000/_xtdb/_dev/query\?valid-time=(.*)"),
        json=[[scan_profile]],
        status_code=200,
    )
    response = client.get("/_dev/scan_profiles", params={"valid_time": str(valid_time)})
    assert response.status_code == 200
    assert response.json() == [
        {"level": 0, "reference": "Hostname|internet|mispo.es", "scan_profile_type": "empty", "user_id": None}
    ]


def test_create_node(httpx_mock):
    httpx_mock.add_response(
        method="POST", url="http://xtdb:3000/_xtdb/create-node", json={"created": "true"}, status_code=200
    )
    response = client.post("/_dev/node")
    assert response.status_code == 200


def test_delete_node(httpx_mock):
    httpx_mock.add_response(
        method="POST", url="http://xtdb:3000/_xtdb/delete-node", json={"deleted": "true"}, status_code=200
    )
    response = client.delete("/_dev/node")
    assert response.status_code == 200


def test_count_findings_by_severity(httpx_mock, patch_pika, caplog, valid_time):
    logger = logging.getLogger("octopoes")
    logger.propagate = True

    xt_response = [
        [
            "KATFindingType|KAT-NO-DKIM",
            {
                "object_type": "KATFindingType",
                "KATFindingType/risk_severity": "medium",
                "KATFindingType/id": "KAT-NO-DKIM",
                "KATFindingType/description": "This hostname does not support a DKIM record.",
                "KATFindingType/primary_key": "KATFindingType|KAT-NO-DKIM",
                "KATFindingType/risk_score": 6.9,
                "xt/id": "KATFindingType|KAT-NO-DKIM",
            },
            1,
        ],
        ["KATFindingType|KAT-NO-FINDING-TYPE", None, 2],
    ]

    httpx_mock.add_response(
        method="POST",
        url=re.compile(r"http://xtdb:3000/_xtdb/_dev/query\?valid-time=(.*)"),
        json=xt_response,
        status_code=200,
    )
    with caplog.at_level(logging.WARNING):
        response = client.get("/_dev/findings/count_by_severity", params={"valid_time": str(valid_time)})
    assert response.status_code == 200
    assert response.json() == {
        "critical": 0,
        "high": 0,
        "medium": 1,
        "low": 0,
        "recommendation": 0,
        "pending": 2,
        "unknown": 0,
    }

    assert len(caplog.record_tuples) == 1
    logger, level, message = caplog.record_tuples[0]
    assert logger == "octopoes.repositories.ooi_repository"
    assert level == logging.WARNING
    assert (
        "There are 2 KATFindingType|KAT-NO-FINDING-TYPE findings but the finding type is not in the database" in message
    )
