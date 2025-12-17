from pytest_django.asserts import assertContains

from objects.models import Hostname, IPAddress, Network
from objects.views import HostnameDetailView, IPAddressDetailView, NetworkDetailView
from tests.conftest import setup_request


def test_network_detail_view(rf, superuser, xtdb):
    network = Network.objects.create(name="internettest")

    request = setup_request(rf.get("objects:network_detail"), superuser)
    response = NetworkDetailView.as_view()(request, pk=network.pk)

    assert response.status_code == 200
    assertContains(response, "internettest")


def test_hostname_detail_view(rf, superuser, xtdb):
    network = Network.objects.create(name="internettest")
    host = Hostname.objects.create(name="testssl.com", network=network)

    request = setup_request(rf.get("objects:hostname_detail"), superuser)
    response = HostnameDetailView.as_view()(request, pk=host.pk)

    assert response.status_code == 200
    assertContains(response, "testssl.com")
    assertContains(response, "internettest")


def test_ipaddress_detail_view(rf, superuser, xtdb):
    network = Network.objects.create(name="internettest")
    ip = IPAddress.objects.create(ip_address="127.0.0.1", network=network)

    request = setup_request(rf.get("objects:ipaddress_detail"), superuser)
    response = IPAddressDetailView.as_view()(request, pk=ip.pk)

    assert response.status_code == 200
    assertContains(response, "127.0.0.1")
    assertContains(response, "internettest")
