import pytest
from django.contrib.contenttypes.models import ContentType
from pytest_django.asserts import assertContains, assertNotContains

from objects.models import Hostname, IPAddress, Network, XTDBOrganization
from tasks.models import ObjectSet
from tasks.views import ObjectSetDetailView
from tests.conftest import setup_request


def test_traverse_objects_with_static_objects(xtdb):
    network = Network.objects.create(name="internet")

    hostname1 = Hostname.objects.create(network=network, name="test1.example.com")
    hostname2 = Hostname.objects.create(network=network, name="test2.example.com")
    Hostname.objects.create(network=network, name="test3.example.com")

    object_set = ObjectSet.objects.create(
        name="Test Set",
        object_type=ContentType.objects.get_for_model(Hostname),
        static_objects=[hostname1.pk, hostname2.pk],
    )

    assert set(object_set.traverse_objects()) == {hostname1.pk, hostname2.pk}


def test_object_set_detail_view(rf, superuser, organization, organization_b):
    network = Network.objects.create(name="internet")

    hostname1 = Hostname.objects.create(network=network, name="test1.example.com")
    hostname2 = Hostname.objects.create(network=network, name="test2.example.com")
    Hostname.objects.create(network=network, name="test3.example.com")

    object_set = ObjectSet.objects.create(
        name="Test Set",
        object_type=ContentType.objects.get_for_model(Hostname),
        static_objects=[hostname1.pk, hostname2.pk],
    )

    request = setup_request(rf.get("object_set_detail"), superuser)
    response = ObjectSetDetailView.as_view()(request, pk=object_set.pk)

    assert response.status_code == 200
    assertContains(response, "Test Set")
    assertContains(response, "test1.example.com")
    assertContains(response, "test2.example.com")
    assertNotContains(response, "test3.example.com")


def test_traverse_objects_with_query(xtdb):
    network = Network.objects.create(name="internet")

    hostname1 = Hostname.objects.create(network=network, name="test1.example.com")
    hostname2 = Hostname.objects.create(network=network, name="test2.example.com")
    Hostname.objects.create(network=network, name="prod.example.com")

    object_set = ObjectSet.objects.create(
        name="Test Set", object_type=ContentType.objects.get_for_model(Hostname), object_query='name ~ "test"'
    )

    assert set(object_set.traverse_objects()) == {hostname1.pk, hostname2.pk}
    assert set(object_set.traverse_objects(pk__in=[hostname1.pk])) == {hostname1.pk}


def test_traverse_objects_combines_static_objects_and_query(xtdb):
    network = Network.objects.create(name="internet")

    Hostname.objects.create(network=network, name="test1.example.com")
    Hostname.objects.create(network=network, name="test2.example.com")
    hostname3 = Hostname.objects.create(network=network, name="prod.example.com")
    Hostname.objects.create(network=network, name="dev.example.com")

    object_set = ObjectSet.objects.create(
        name="Combined Set",
        object_type=ContentType.objects.get_for_model(Hostname),
        static_objects=[hostname3.pk],
        object_query="",
    )

    result = object_set.traverse_objects()
    assert len(result) >= 1
    assert hostname3.pk in result


def test_traverse_objects_removes_duplicates(xtdb):
    network = Network.objects.create(name="internet")
    hostname1 = Hostname.objects.create(network=network, name="test1.example.com")
    object_set = ObjectSet.objects.create(
        name="Duplicate Set",
        object_type=ContentType.objects.get_for_model(Hostname),
        static_objects=[hostname1.pk],
        object_query='name = "test1.example.com"',
    )

    result = object_set.traverse_objects()
    assert len(result) == 1
    assert hostname1.pk in result


@pytest.mark.django_db
def test_traverse_objects_empty_set():
    object_set = ObjectSet.objects.create(
        name="Empty Set", object_type=ContentType.objects.get_for_model(Hostname), static_objects=[]
    )

    result = object_set.traverse_objects()
    assert len(result) == 0


def test_traverse_objects_invalid_query(xtdb):
    network = Network.objects.create(name="internet")
    hostname1 = Hostname.objects.create(network=network, name="test1.example.com")

    object_set = ObjectSet.objects.create(
        name="Invalid Query Set",
        object_type=ContentType.objects.get_for_model(Hostname),
        static_objects=[hostname1.pk],
        object_query="invalid query syntax!!!",
    )

    result = object_set.traverse_objects()
    assert len(result) == 2  # Root domain gets saved as well
    assert hostname1.pk in result


def test_object_set_detail_view_filters_by_organization_for_ipaddresses(
    rf, client_member, superuser_member, organization, organization_b, xtdb
):
    """Test that ObjectSet detail view only shows IP addresses from the selected organization.
    Objects from other organizations should not be shown even if they match the object set query."""
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

    # Create object set with query that matches all IP addresses
    ipaddress_ct = ContentType.objects.get_for_model(IPAddress)
    object_set = ObjectSet.objects.create(
        name="All IP Addresses",
        object_type=ipaddress_ct,
        object_query="",  # Empty query matches all objects
    )

    # Test 1: Superuser WITHOUT organization filter should see ALL objects
    request = setup_request(rf.get("object_set_detail"), superuser_member.user)
    response = ObjectSetDetailView.as_view()(request, pk=object_set.pk)

    assert response.status_code == 200
    # Superuser should see all IP addresses from both organizations
    assertContains(response, "1.1.1.1")
    assertContains(response, "2.2.2.2")
    assertContains(response, "3.3.3.3")
    assertContains(response, "4.4.4.4")

    # Test 2: Superuser WITH organization filter should see only filtered organization's objects
    request = setup_request(rf.get("object_set_detail", {"organization": organization.code}), superuser_member.user)
    response = ObjectSetDetailView.as_view()(request, pk=object_set.pk)

    assert response.status_code == 200
    # Should contain IP addresses from organization A only
    assertContains(response, "1.1.1.1")
    assertContains(response, "2.2.2.2")
    # Should NOT contain IP addresses from organization B
    assertNotContains(response, "3.3.3.3")
    assertNotContains(response, "4.4.4.4")

    # Test 3: Client member WITH organization filter should see only their organization's objects
    request = setup_request(rf.get("object_set_detail", {"organization": organization.code}), client_member.user)
    response = ObjectSetDetailView.as_view()(request, pk=object_set.pk)

    assert response.status_code == 200

    # Should contain IP addresses from organization A
    assertContains(response, "1.1.1.1")
    assertContains(response, "2.2.2.2")

    # Should NOT contain IP addresses from organization B
    assertNotContains(response, "3.3.3.3")
    assertNotContains(response, "4.4.4.4")


def test_object_set_detail_view_filters_by_organization_for_hostnames(
    rf, client_member, superuser_member, organization, organization_b, xtdb
):
    """Test that ObjectSet detail view only shows hostnames from the selected organization.
    Objects from other organizations should not be shown even if they match the object set query."""
    network = Network.objects.create(name="internet")

    # Create hostnames for organization A
    h1_org_a = Hostname.objects.create(name="test1.example.com", network=network)
    h1_org_a.organizations.add(XTDBOrganization.objects.get(pk=organization.pk))

    h2_org_a = Hostname.objects.create(name="test2.example.com", network=network)
    h2_org_a.organizations.add(XTDBOrganization.objects.get(pk=organization.pk))

    # Create hostnames for organization B
    h1_org_b = Hostname.objects.create(name="test3.example.com", network=network)
    h1_org_b.organizations.add(XTDBOrganization.objects.get(pk=organization_b.pk))

    h2_org_b = Hostname.objects.create(name="test4.example.com", network=network)
    h2_org_b.organizations.add(XTDBOrganization.objects.get(pk=organization_b.pk))

    # Create object set with query that matches all hostnames
    hostname_ct = ContentType.objects.get_for_model(Hostname)
    object_set = ObjectSet.objects.create(
        name="All Hostnames",
        object_type=hostname_ct,
        object_query="",  # Empty query matches all objects
    )

    # Test 1: Superuser WITHOUT organization filter should see ALL objects
    request = setup_request(rf.get("object_set_detail"), superuser_member.user)
    response = ObjectSetDetailView.as_view()(request, pk=object_set.pk)

    assert response.status_code == 200
    # Superuser should see all hostnames from both organizations
    assertContains(response, "test1.example.com")
    assertContains(response, "test2.example.com")
    assertContains(response, "test3.example.com")
    assertContains(response, "test4.example.com")

    # Test 2: Superuser WITH organization filter should see only filtered organization's objects
    request = setup_request(rf.get("object_set_detail", {"organization": organization.code}), superuser_member.user)
    response = ObjectSetDetailView.as_view()(request, pk=object_set.pk)

    assert response.status_code == 200
    # Should contain hostnames from organization A only
    assertContains(response, "test1.example.com")
    assertContains(response, "test2.example.com")
    # Should NOT contain hostnames from organization B
    assertNotContains(response, "test3.example.com")
    assertNotContains(response, "test4.example.com")

    # Test 3: Client member WITH organization filter should see only their organization's objects
    request = setup_request(rf.get("object_set_detail", {"organization": organization.code}), client_member.user)
    response = ObjectSetDetailView.as_view()(request, pk=object_set.pk)

    assert response.status_code == 200

    # Should contain hostnames from organization A
    assertContains(response, "test1.example.com")
    assertContains(response, "test2.example.com")

    # Should NOT contain hostnames from organization B
    assertNotContains(response, "test3.example.com")
    assertNotContains(response, "test4.example.com")
