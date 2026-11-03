import json
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied
from django.test import Client

from rocky.health import ServiceHealth
from rocky.views.health import GlobalHealthChecks, GlobalHealthView, flatten_health
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


def test_global_health_endpoint_healthy(rf, client_member):
    """The non-org-scoped health endpoint returns 200 with service health when all services are up (#4231)."""
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
        response.render()

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["service"] == "rocky"
    assert data["healthy"] is True
    assert data["version"] is None  # version stripped from public endpoint
    assert {s["service"] for s in data["results"]} == {"octopoes", "katalogus", "scheduler", "bytes"}
    assert all(s["version"] is None for s in data["results"])


def test_global_health_endpoint_unhealthy_returns_503(rf, client_member):
    """The endpoint returns 503 when a backing service is down so LBs can act on the status code (#4231)."""
    mock_services = [
        ServiceHealth(service="octopoes", healthy=False, additional="down"),
        ServiceHealth(service="katalogus", healthy=True),
        ServiceHealth(service="scheduler", healthy=True),
        ServiceHealth(service="bytes", healthy=True),
    ]
    with (
        patch("rocky.views.health.get_octopoes_root_health", return_value=mock_services[0]),
        patch("rocky.views.health.get_katalogus_health", return_value=mock_services[1]),
        patch("rocky.views.health.get_scheduler_health", return_value=mock_services[2]),
        patch("rocky.views.health.get_bytes_health", return_value=mock_services[3]),
    ):
        request = setup_request(rf.get("global_health"), client_member.user)
        response = GlobalHealthView.as_view()(request)
        response.render()

    assert response.status_code == 503
    data = json.loads(response.content)
    assert data["healthy"] is False


def test_global_health_endpoint_anonymous_via_url(db):
    """The endpoint is reachable anonymously through the real URL — pins routing, auth, and trailing slash (#4231)."""
    with (
        patch(
            "rocky.views.health.get_octopoes_root_health", return_value=ServiceHealth(service="octopoes", healthy=True)
        ),
        patch("rocky.views.health.get_katalogus_health", return_value=ServiceHealth(service="katalogus", healthy=True)),
        patch("rocky.views.health.get_scheduler_health", return_value=ServiceHealth(service="scheduler", healthy=True)),
        patch("rocky.views.health.get_bytes_health", return_value=ServiceHealth(service="bytes", healthy=True)),
    ):
        response = Client(SERVER_NAME="localhost").get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "rocky"
    assert data["healthy"] is True
    assert data["version"] is None
    # Finding A: public endpoint must not leak additional/results that fingerprint
    assert all(s["additional"] is None for s in data["results"])
    assert all(s["results"] == [] for s in data["results"])


def test_global_health_endpoint_trailing_slash(db):
    """Both /api/v1/health and /api/v1/health/ resolve — no 404 on the slashed form (#4231)."""
    with (
        patch(
            "rocky.views.health.get_octopoes_root_health", return_value=ServiceHealth(service="octopoes", healthy=True)
        ),
        patch("rocky.views.health.get_katalogus_health", return_value=ServiceHealth(service="katalogus", healthy=True)),
        patch("rocky.views.health.get_scheduler_health", return_value=ServiceHealth(service="scheduler", healthy=True)),
        patch("rocky.views.health.get_bytes_health", return_value=ServiceHealth(service="bytes", healthy=True)),
    ):
        response = Client(SERVER_NAME="localhost").get("/api/v1/health/")

    assert response.status_code == 200


def test_global_health_endpoint_unhealthy_via_url(db):
    """The real URL returns 503 when Octopoes is down — pins finding #2 through routing (#4231)."""
    with (
        patch(
            "rocky.views.health.get_octopoes_root_health",
            return_value=ServiceHealth(service="octopoes", healthy=False, additional="down"),
        ),
        patch("rocky.views.health.get_katalogus_health", return_value=ServiceHealth(service="katalogus", healthy=True)),
        patch("rocky.views.health.get_scheduler_health", return_value=ServiceHealth(service="scheduler", healthy=True)),
        patch("rocky.views.health.get_bytes_health", return_value=ServiceHealth(service="bytes", healthy=True)),
    ):
        response = Client(SERVER_NAME="localhost").get("/api/v1/health")

    assert response.status_code == 503
    assert response.json()["healthy"] is False


def test_global_health_beautified(rf, superuser):
    """The non-org-scoped beautified health page renders for superusers (#4231)."""
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
        request = setup_request(rf.get("global_health_beautified"), superuser)
        response = GlobalHealthChecks.as_view()(request)
        response.render()

    assert response.status_code == 200
    assert b"Health Checks" in response.content


def test_global_health_beautified_denied_for_non_superuser(rf, client_member):
    """The beautified page is superuser-only (#4231) — a plain member must not reach it."""
    request = setup_request(rf.get("global_health_beautified"), client_member.user)

    with pytest.raises(PermissionDenied):
        GlobalHealthChecks.as_view()(request)
