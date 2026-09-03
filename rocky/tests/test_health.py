import json
from unittest.mock import patch

from rocky.health import ServiceHealth
from rocky.views.health import GlobalHealthView, flatten_health
from tests.conftest import setup_request


def test_flatten_health_simple():
    mock_health = ServiceHealth(service="service1", healthy=True, version="1.1.1")
    assert flatten_health(mock_health) == [ServiceHealth(service="service1", healthy=True, version="1.1.1")]


def test_flatten_health_recursive():
    mock_health = ServiceHealth(
        service="service1",
        healthy=True,
        version="1.1.1",
        results=[ServiceHealth(service="service2", healthy=False, version="2.2.2")],
    )
    assert flatten_health(mock_health) == [
        ServiceHealth(service="service1", healthy=True, version="1.1.1"),
        ServiceHealth(service="service2", healthy=False, version="2.2.2"),
    ]


def test_global_health_endpoint(rf, client_member):
    """The non-org-scoped health endpoint returns service health without requiring an organization (#4231)."""
    mock_services = [
        ServiceHealth(service="octopoes", healthy=True, version="1.0"),
        ServiceHealth(service="katalogus", healthy=True, version="1.0"),
        ServiceHealth(service="scheduler", healthy=True, version="1.0"),
        ServiceHealth(service="bytes", healthy=True, version="1.0"),
    ]
    with (
        patch("rocky.views.health.get_octopoes_root_health", return_value=mock_services[0]),
        patch("rocky.views.health.get_katalogus_health", return_value=mock_services[1]),
        patch("rocky.views.health.get_scheduler_health", return_value=mock_services[2]),
        patch("rocky.views.health.get_bytes_health", return_value=mock_services[3]),
    ):
        request = setup_request(rf.get("global_health"), client_member.user)
        response = GlobalHealthView.as_view()(request)

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["service"] == "rocky"
    assert data["healthy"] is True
    assert {s["service"] for s in data["results"]} == {"octopoes", "katalogus", "scheduler", "bytes"}
