from urllib.parse import quote

from django.contrib.contenttypes.models import ContentType
from pytest_django.asserts import assertContains, assertNotContains

from objects.models import Hostname, IPAddress, IPPort, Network, Protocol, Software, XTDBOrganization
from objects.views import HostnameListView, IPAddressListView, IPPortSoftwareDeleteView
from tasks.models import ObjectSet
from tests.conftest import setup_request


def test_hostname_scan_bulk_action(rf, superuser_member, xtdb):
    network = Network.objects.create(name="internet")
    h1 = Hostname.objects.create(name="test1.com", network=network, scan_level=2)
    h2 = Hostname.objects.create(name="test2.com", network=network, scan_level=2)

    request = setup_request(
        rf.post("objects:hostname_list", data={"hostname": [str(h1.pk), str(h2.pk)], "action": "scan"}),
        superuser_member.user,
    )
    response = HostnameListView.as_view()(request)

    assert response.status_code == 302
    assert "/tasks/add/" in response.url
    assert f"input_hostnames={quote(h1.pk)}" in response.url
    assert f"input_hostnames={quote(h2.pk)}" in response.url


def test_hostname_create_object_set_bulk_action(rf, superuser_member, xtdb):
    network = Network.objects.create(name="internet")
    h1 = Hostname.objects.create(name="test1.com", network=network)
    h2 = Hostname.objects.create(name="test2.com", network=network)

    request = setup_request(
        rf.post("objects:hostname_list", data={"hostname": [str(h1.pk), str(h2.pk)], "action": "create-object-set"}),
        superuser_member.user,
    )
    response = HostnameListView.as_view()(request)

    assert response.status_code == 302
    assert "/object-sets/add" in response.url
    hostname_ct = ContentType.objects.get_for_model(Hostname)
    assert f"object_type={hostname_ct.pk}" in response.url
    assert f"objects={quote(h1.pk)}" in response.url
    assert f"objects={quote(h2.pk)}" in response.url


def test_ipaddress_scan_bulk_action(rf, superuser_member, xtdb):
    network = Network.objects.create(name="internet")
    ip1 = IPAddress.objects.create(address="1.1.1.1", network=network, scan_level=2)
    ip2 = IPAddress.objects.create(address="2.2.2.2", network=network, scan_level=2)

    request = setup_request(
        rf.post("objects:ipaddress_list", data={"ipaddress": [str(ip1.pk), str(ip2.pk)], "action": "scan"}),
        superuser_member.user,
    )
    response = IPAddressListView.as_view()(request)

    assert response.status_code == 302
    assert "/tasks/add/" in response.url
    assert f"input_ips={quote(ip1.pk)}" in response.url
    assert f"input_ips={quote(ip2.pk)}" in response.url


def test_ipaddress_create_object_set_bulk_action(rf, superuser_member, xtdb):
    network = Network.objects.create(name="internet")
    ip1 = IPAddress.objects.create(address="1.1.1.1", network=network)
    ip2 = IPAddress.objects.create(address="2.2.2.2", network=network)

    request = setup_request(
        rf.post(
            "objects:ipaddress_list", data={"ipaddress": [str(ip1.pk), str(ip2.pk)], "action": "create-object-set"}
        ),
        superuser_member.user,
    )
    response = IPAddressListView.as_view()(request)

    assert response.status_code == 302
    assert "/object-sets/add" in response.url
    ipaddress_ct = ContentType.objects.get_for_model(IPAddress)
    assert f"object_type={ipaddress_ct.pk}" in response.url
    assert f"objects={quote(ip1.pk)}" in response.url
    assert f"objects={quote(ip2.pk)}" in response.url


def test_hostname_delete_bulk_action(rf, superuser_member, xtdb):
    network = Network.objects.create(name="internet")
    h1 = Hostname.objects.create(name="test1.com", network=network)
    h2 = Hostname.objects.create(name="test2.com", network=network)
    h3 = Hostname.objects.create(name="test3.com", network=network)

    assert Hostname.objects.count() == 3

    request = setup_request(
        rf.post("objects:hostname_list", data={"hostname": [str(h1.pk), str(h2.pk)], "action": "delete"}),
        superuser_member.user,
    )
    response = HostnameListView.as_view()(request)

    assert response.status_code == 302

    assert Hostname.objects.count() == 1
    assert Hostname.objects.filter(pk=h3.pk).exists()
    assert not Hostname.objects.filter(pk=h1.pk).exists()
    assert not Hostname.objects.filter(pk=h2.pk).exists()


def test_ipaddress_set_scan_level_bulk_action(rf, superuser_member, xtdb):
    network = Network.objects.create(name="internet")
    ip1 = IPAddress.objects.create(address="1.1.1.1", network=network, scan_level=1)
    ip2 = IPAddress.objects.create(address="2.2.2.2", network=network, scan_level=1)

    request = setup_request(
        rf.post(
            "objects:ipaddress_list",
            data={
                "ipaddress": [str(ip1.pk), str(ip2.pk)],
                "action": "set-scan-level",
                "scan_level": "3",
                "declared": "declared",
            },
        ),
        superuser_member.user,
    )
    response = IPAddressListView.as_view()(request)

    assert response.status_code == 302
    ip1.refresh_from_db()
    ip2.refresh_from_db()
    assert ip1.scan_level == 3
    assert ip2.scan_level == 3


def test_ipport_software_delete(rf, superuser_member, xtdb):
    network = Network.objects.create(name="internet")
    ip = IPAddress.objects.create(address="1.1.1.1", network=network)
    port = IPPort.objects.create(address=ip, protocol=Protocol.TCP, port=22, tls=False, service="ssh")
    software = Software.objects.create(name="openssh", version="8.0")
    port.software.add(software)

    assert port.software.count() == 1
    assert software in port.software.all()

    request = setup_request(
        rf.post("objects:delete_ipport_software", kwargs={"port_pk": str(port.pk), "pk": str(software.pk)}),
        superuser_member.user,
    )
    response = IPPortSoftwareDeleteView.as_view()(request, port_pk=str(port.pk), pk=str(software.pk))

    assert response.status_code == 302
    assert f"/objects/ipaddress/{quote(ip.pk)}/" in response.url
    port.refresh_from_db()
    assert port.software.count() == 0
    assert software not in port.software.all()


def test_ipaddress_list_view_filtered_by_object_set_and_organization(
    rf, superuser_member, client_member, organization, organization_b, xtdb
):
    network = Network.objects.create(name="internet")

    # Create IP addresses for organization A
    ip1_org_a = IPAddress.objects.create(address="1.1.1.1", network=network)
    ip1_org_a.organizations.add(XTDBOrganization.objects.get(pk=organization.pk))

    ip2_org_a = IPAddress.objects.create(address="2.2.2.2", network=network)
    ip2_org_a.organizations.add(XTDBOrganization.objects.get(pk=organization.pk))

    # Create IP addresses for organization B
    ip1_org_b = IPAddress.objects.create(address="3.3.3.3", network=network)
    ip1_org_b.organizations.add(XTDBOrganization.objects.get(pk=organization_b.pk))

    ip2_org_b = IPAddress.objects.create(address="4.4.4.4", network=network)
    ip2_org_b.organizations.add(XTDBOrganization.objects.get(pk=organization_b.pk))

    # Create an object set that matches all IP addresses (using empty query which matches all)
    ipaddress_ct = ContentType.objects.get_for_model(IPAddress)
    object_set = ObjectSet.objects.create(
        name="Test IP Set",
        object_type=ipaddress_ct,
        object_query="",  # Empty query matches all objects
    )

    # Request list view with object set filter AND organization filter
    request = setup_request(
        rf.get("objects:ipaddress_list", {"object_set": object_set.pk, "organization": organization.code}),
        client_member.user,
    )
    response = IPAddressListView.as_view()(request)
    assert response.status_code == 200

    assertContains(response, "1.1.1.1")
    assertContains(response, "2.2.2.2")
    assertNotContains(response, "3.3.3.3")
    assertNotContains(response, "4.4.4.4")

    # Organization code filter not necessary for client member
    request = setup_request(rf.get("objects:ipaddress_list", {"object_set": object_set.pk}), client_member.user)
    response = IPAddressListView.as_view()(request)
    assert response.status_code == 200

    assertContains(response, "1.1.1.1")
    assertContains(response, "2.2.2.2")
    assertNotContains(response, "3.3.3.3")
    assertNotContains(response, "4.4.4.4")

    # superusers see everything
    request = setup_request(rf.get("objects:ipaddress_list", {"object_set": object_set.pk}), superuser_member.user)
    response = IPAddressListView.as_view()(request)
    assert response.status_code == 200

    assertContains(response, "1.1.1.1")
    assertContains(response, "2.2.2.2")
    assertContains(response, "3.3.3.3")
    assertContains(response, "4.4.4.4")

    # except when filtered
    request = setup_request(
        rf.get("objects:ipaddress_list", {"object_set": object_set.pk, "organization": organization.code}),
        superuser_member.user,
    )
    response = IPAddressListView.as_view()(request)
    assert response.status_code == 200

    assertContains(response, "1.1.1.1")
    assertContains(response, "2.2.2.2")
    assertNotContains(response, "3.3.3.3")
    assertNotContains(response, "4.4.4.4")


def test_hostname_list_view_filtered_by_object_set_and_organization(
    rf, superuser_member, client_member, organization, organization_b, xtdb
):
    network = Network.objects.create(name="internet")

    # Create hostnames for organization A
    h1_org_a = Hostname.objects.create(name="test1.example.com", network=network)
    h1_org_a.organizations.add(XTDBOrganization.objects.get(pk=organization.pk))

    h2_org_b = Hostname.objects.create(name="test2.example.com", network=network)
    h2_org_b.organizations.add(XTDBOrganization.objects.get(pk=organization_b.pk))

    # Create an object set that matches all hostnames (using empty query which matches all)
    hostname_ct = ContentType.objects.get_for_model(Hostname)
    object_set = ObjectSet.objects.create(
        name="Test Hostname Set",
        object_type=hostname_ct,
        object_query="",  # Empty query matches all objects
    )

    # Request list view with object set filter AND organization filter
    request = setup_request(
        rf.get("objects:hostname_list", {"object_set": object_set.pk, "organization": organization.code}),
        client_member.user,
    )
    response = HostnameListView.as_view()(request)

    assertContains(response, "test1.example.com")
    assertNotContains(response, "test2.example.com")

    # Request list view with object set filter AND organization filter
    request = setup_request(rf.get("objects:hostname_list", {"object_set": object_set.pk}), client_member.user)
    response = HostnameListView.as_view()(request)

    assertContains(response, "test1.example.com")
    assertNotContains(response, "test2.example.com")

    # Request list view with object set filter AND organization filter
    request = setup_request(
        rf.get("objects:hostname_list", {"object_set": object_set.pk, "organization": organization.code}),
        superuser_member.user,
    )
    response = HostnameListView.as_view()(request)

    assertContains(response, "test1.example.com")
    assertNotContains(response, "test2.example.com")

    # Request list view with object set filter AND organization filter
    request = setup_request(rf.get("objects:hostname_list", {"object_set": object_set.pk}), superuser_member.user)
    response = HostnameListView.as_view()(request)

    assertContains(response, "test1.example.com")
    assertContains(response, "test2.example.com")
