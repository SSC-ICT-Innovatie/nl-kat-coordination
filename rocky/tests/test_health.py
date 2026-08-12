from rocky.health import ServiceHealth
from rocky.views.health import flatten_health


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
