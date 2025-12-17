"""Tests for organization management features on Network, IPAddress, and Hostname objects."""

from io import BytesIO

from pytest_django.asserts import assertContains

from objects.models import Hostname, IPAddress, Network, XTDBOrganization
from objects.views import (
    GenericAssetCreateView,
    GenericAssetCSVUploadView,
    HostnameCreateView,
    HostnameCSVUploadView,
    HostnameDetailView,
    HostnameManageOrganizationsView,
    IPAddressCreateView,
    IPAddressCSVUploadView,
    IPAddressDetailView,
    IPAddressManageOrganizationsView,
    NetworkCreateView,
    NetworkDetailView,
    NetworkManageOrganizationsView,
)
from openkat.models import Organization
from tests.conftest import setup_request


def test_ipaddress_csv_upload_with_organization_id(rf, superuser_member, xtdb):
    org = Organization.objects.create(name="Test Org")
    xtdb_org = XTDBOrganization.objects.get(pk=org.pk)
    csv_content = f"192.168.1.1,{org.pk}\n10.0.0.1,{org.pk}"
    csv_file = BytesIO(csv_content.encode())
    csv_file.name = "ip_addresses.csv"

    request = setup_request(rf.post("objects:ipaddress_csv_upload", {"csv_file": csv_file}), superuser_member.user)
    response = IPAddressCSVUploadView.as_view()(request)

    assert response.status_code == 302
    assert IPAddress.objects.count() == 2

    # Check that organizations were assigned
    ip1 = IPAddress.objects.get(ip_address="192.168.1.1")
    ip2 = IPAddress.objects.get(ip_address="10.0.0.1")
    assert xtdb_org in ip1.organizations.all()
    assert xtdb_org in ip2.organizations.all()

    messages = list(request._messages)
    assert any("Successfully set organizations for 2 IP addresses" in str(m) for m in messages)


def test_ipaddress_csv_upload_without_organization_id(rf, superuser_member, xtdb):
    """Test CSV upload without organization id works as before."""
    csv_content = b"192.168.1.1\n10.0.0.1"
    csv_file = BytesIO(csv_content)
    csv_file.name = "ip_addresses.csv"

    request = setup_request(rf.post("objects:ipaddress_csv_upload", {"csv_file": csv_file}), superuser_member.user)
    response = IPAddressCSVUploadView.as_view()(request)

    assert response.status_code == 302
    assert IPAddress.objects.count() == 2

    # Check that no organizations were assigned
    ip1 = IPAddress.objects.get(ip_address="192.168.1.1")
    ip2 = IPAddress.objects.get(ip_address="10.0.0.1")
    assert ip1.organizations.count() == 0
    assert ip2.organizations.count() == 0


def test_ipaddress_csv_upload_with_invalid_organization_id(rf, superuser_member, xtdb):
    """Test CSV upload with invalid organization id shows warning but creates IP."""
    csv_content = b"192.168.1.1,123456789\n10.0.0.1"
    csv_file = BytesIO(csv_content)
    csv_file.name = "ip_addresses.csv"

    request = setup_request(rf.post("objects:ipaddress_csv_upload", {"csv_file": csv_file}), superuser_member.user)
    response = IPAddressCSVUploadView.as_view()(request)

    assert response.status_code == 302
    assert IPAddress.objects.count() == 2

    # Check that IP was created but no organization assigned
    ip1 = IPAddress.objects.get(ip_address="192.168.1.1")
    assert ip1.organizations.count() == 0

    messages = list(request._messages)
    assert any("Organization with id '123456789' not found" in str(m) for m in messages)


def test_hostname_csv_upload_with_organization_id(rf, superuser_member, xtdb):
    """Test hostname CSV upload with organization id."""
    org = Organization.objects.create(name="Test Org")
    xtdb_org = XTDBOrganization.objects.get(pk=org.pk)
    csv_content = f"example.com,{org.pk}\ntest.org,{org.pk}"
    csv_file = BytesIO(csv_content.encode())
    csv_file.name = "hostnames.csv"

    request = setup_request(rf.post("objects:hostname_csv_upload", {"csv_file": csv_file}), superuser_member.user)
    response = HostnameCSVUploadView.as_view()(request)

    assert response.status_code == 302
    assert Hostname.objects.count() == 2

    # Check that organizations were assigned
    host1 = Hostname.objects.get(name="example.com")
    host2 = Hostname.objects.get(name="test.org")
    assert xtdb_org in host1.organizations.all()
    assert xtdb_org in host2.organizations.all()

    messages = list(request._messages)
    assert any("Successfully set organizations for 2 hostnames" in str(m) for m in messages)


def test_hostname_csv_upload_without_organization_id(rf, superuser_member, xtdb):
    """Test hostname CSV upload without organization id."""
    csv_content = b"example.com\ntest.org"
    csv_file = BytesIO(csv_content)
    csv_file.name = "hostnames.csv"

    request = setup_request(rf.post("objects:hostname_csv_upload", {"csv_file": csv_file}), superuser_member.user)
    response = HostnameCSVUploadView.as_view()(request)

    assert response.status_code == 302
    assert Hostname.objects.count() == 2

    # Check that no organizations were assigned
    host1 = Hostname.objects.get(name="example.com")
    host2 = Hostname.objects.get(name="test.org")
    assert host1.organizations.count() == 0
    assert host2.organizations.count() == 0


def test_hostname_csv_upload_mixed_organization_ids(rf, superuser_member, xtdb):
    """Test hostname CSV upload with mixed organization ids (some with, some without)."""
    org = Organization.objects.create(name="Test Org")
    xtdb_org = XTDBOrganization.objects.get(pk=org.pk)
    csv_content = f"example.com,{org.pk}\ntest.org\nfoo.com,{org.pk}"
    csv_file = BytesIO(csv_content.encode())
    csv_file.name = "hostnames.csv"

    request = setup_request(rf.post("objects:hostname_csv_upload", {"csv_file": csv_file}), superuser_member.user)
    response = HostnameCSVUploadView.as_view()(request)

    assert response.status_code == 302
    assert Hostname.objects.count() == 3

    # Check that organizations were assigned correctly
    host1 = Hostname.objects.get(name="example.com")
    host2 = Hostname.objects.get(name="test.org")
    host3 = Hostname.objects.get(name="foo.com")
    assert xtdb_org in host1.organizations.all()
    assert host2.organizations.count() == 0
    assert xtdb_org in host3.organizations.all()


def test_generic_asset_csv_upload_with_organization_id(rf, superuser_member, xtdb):
    """Test generic asset CSV upload with organization id in third column."""
    org = Organization.objects.create(name="Test Org")
    xtdb_org = XTDBOrganization.objects.get(pk=org.pk)
    csv_content = f"192.168.1.1,2,{org.pk}\nexample.com,3,{org.pk}"
    csv_file = BytesIO(csv_content.encode())
    csv_file.name = "assets.csv"

    request = setup_request(rf.post("objects:generic_asset_csv_upload", {"csv_file": csv_file}), superuser_member.user)
    response = GenericAssetCSVUploadView.as_view()(request)

    assert response.status_code == 302
    assert IPAddress.objects.count() == 1
    assert Hostname.objects.count() == 1

    # Check that organizations were assigned
    ip = IPAddress.objects.get(ip_address="192.168.1.1")
    host = Hostname.objects.get(name="example.com")
    assert xtdb_org in ip.organizations.all()
    assert xtdb_org in host.organizations.all()

    # Check scan levels were set
    assert ip.scan_level == 2
    assert host.scan_level == 3

    messages = list(request._messages)
    assert any("Successfully set organizations for 2 assets" in str(m) for m in messages)


# Single Create Tests with Organizations


def test_network_create_view_has_organizations_field(rf, superuser_member, xtdb):
    """Test that network create view includes organizations field."""
    view = NetworkCreateView()
    assert "organizations" in view.fields


def test_ipaddress_create_view_has_organizations_field(rf, superuser_member, xtdb):
    """Test that IP address create view includes organizations field."""
    view = IPAddressCreateView()
    assert "organizations" in view.fields


def test_hostname_create_view_has_organizations_field(rf, superuser_member, xtdb):
    """Test that hostname create view includes organizations field."""
    view = HostnameCreateView()
    assert "organizations" in view.fields


# Bulk Create Tests with Organizations


def test_generic_asset_bulk_create_with_organizations(rf, superuser_member, xtdb):
    """Test generic asset bulk create with organizations."""
    org = Organization.objects.create(name="Test Org")
    xtdb_org = XTDBOrganization.objects.get(pk=org.pk)
    network = Network.objects.create(name="internet")

    request = setup_request(
        rf.post(
            "objects:generic_asset_create",
            {"assets": "192.168.1.1\nexample.com\n10.0.0.1", "network": network.pk, "organizations": [org.pk]},
        ),
        superuser_member.user,
    )
    response = GenericAssetCreateView.as_view()(request)

    assert response.status_code == 302
    assert IPAddress.objects.count() == 2
    assert Hostname.objects.count() == 1

    # Check that organizations were assigned
    ip1 = IPAddress.objects.get(ip_address="192.168.1.1")
    ip2 = IPAddress.objects.get(ip_address="10.0.0.1")
    host = Hostname.objects.get(name="example.com")
    assert xtdb_org in ip1.organizations.all()
    assert xtdb_org in ip2.organizations.all()
    assert xtdb_org in host.organizations.all()


def test_generic_asset_bulk_create_without_organizations(rf, superuser_member, xtdb):
    """Test generic asset bulk create without organizations."""
    network = Network.objects.create(name="internet")

    request = setup_request(
        rf.post("objects:generic_asset_create", {"assets": "192.168.1.1\nexample.com", "network": network.pk}),
        superuser_member.user,
    )
    response = GenericAssetCreateView.as_view()(request)

    assert response.status_code == 302
    assert IPAddress.objects.count() == 1
    assert Hostname.objects.count() == 1

    # Check that no organizations were assigned
    ip = IPAddress.objects.get(ip_address="192.168.1.1")
    host = Hostname.objects.get(name="example.com")
    assert ip.organizations.count() == 0
    assert host.organizations.count() == 0


# Detail View Tests


def test_network_detail_view_shows_organizations(rf, superuser_member, xtdb):
    """Test that network detail view displays organizations."""
    org = Organization.objects.create(name="Test Org")
    xtdb_org = XTDBOrganization.objects.get(pk=org.pk)
    network = Network.objects.create(name="test-network")
    network.organizations.add(xtdb_org)

    request = setup_request(rf.get("objects:network_detail"), superuser_member.user)
    response = NetworkDetailView.as_view()(request, pk=network.pk)

    assert response.status_code == 200
    assertContains(response, "Test Org")


def test_network_detail_view_context_includes_all_organizations(rf, superuser_member, xtdb):
    """Test that network detail view context includes all organizations for management form."""
    org1 = Organization.objects.create(name="Org 1")
    org2 = Organization.objects.create(name="Org 2")
    network = Network.objects.create(name="test-network")

    request = setup_request(rf.get("objects:network_detail"), superuser_member.user)
    view = NetworkDetailView()
    view.setup(request, pk=network.pk)
    view.object = network
    context = view.get_context_data()

    assert "all_organizations" in context
    assert org1 in context["all_organizations"]
    assert org2 in context["all_organizations"]


def test_ipaddress_detail_view_shows_organizations(rf, superuser_member, xtdb):
    """Test that IP address detail view displays organizations."""
    org = Organization.objects.create(name="Test Org")
    xtdb_org = XTDBOrganization.objects.get(pk=org.pk)
    network = Network.objects.create(name="internet")
    ip = IPAddress.objects.create(ip_address="192.168.1.1", network=network)
    ip.organizations.add(xtdb_org)

    request = setup_request(rf.get("objects:ipaddress_detail"), superuser_member.user)
    response = IPAddressDetailView.as_view()(request, pk=ip.pk)

    assert response.status_code == 200
    assertContains(response, "Test Org")


def test_hostname_detail_view_shows_organizations(rf, superuser_member, xtdb):
    """Test that hostname detail view displays organizations."""
    org = Organization.objects.create(name="Test Org")
    xtdb_org = XTDBOrganization.objects.get(pk=org.pk)
    network = Network.objects.create(name="internet")
    host = Hostname.objects.create(name="example.com", network=network)
    host.organizations.add(xtdb_org)

    request = setup_request(rf.get("objects:hostname_detail"), superuser_member.user)
    response = HostnameDetailView.as_view()(request, pk=host.pk)

    assert response.status_code == 200
    assertContains(response, "Test Org")


def test_network_manage_organizations_add(rf, superuser_member, xtdb):
    org1 = Organization.objects.create(name="Org 1")
    org2 = Organization.objects.create(name="Org 2")
    xtdb_org1 = XTDBOrganization.objects.get(pk=org1.pk)
    xtdb_org2 = XTDBOrganization.objects.get(pk=org2.pk)
    network = Network.objects.create(name="test-network")

    request = setup_request(
        rf.post("objects:network_manage_organizations", {"organizations": [org1.pk, org2.pk]}), superuser_member.user
    )
    response = NetworkManageOrganizationsView.as_view()(request, pk=network.pk)

    assert response.status_code == 302
    assert network.organizations.count() == 2
    assert xtdb_org1 in network.organizations.all()
    assert xtdb_org2 in network.organizations.all()

    messages = list(request._messages)
    assert any("Organizations updated successfully" in str(m) for m in messages)


def test_network_manage_organizations_update(rf, superuser_member, xtdb):
    """Test updating organizations on a network (replace existing)."""
    org1 = Organization.objects.create(name="Org 1")
    org2 = Organization.objects.create(name="Org 2")
    org3 = Organization.objects.create(name="Org 3")
    xtdb_org1 = XTDBOrganization.objects.get(pk=org1.pk)
    xtdb_org2 = XTDBOrganization.objects.get(pk=org2.pk)
    xtdb_org3 = XTDBOrganization.objects.get(pk=org3.pk)
    network = Network.objects.create(name="test-network")
    network.organizations.add(xtdb_org1, xtdb_org2)

    request = setup_request(
        rf.post("objects:network_manage_organizations", {"organizations": [org2.pk, org3.pk]}), superuser_member.user
    )
    response = NetworkManageOrganizationsView.as_view()(request, pk=network.pk)

    assert response.status_code == 302
    assert network.organizations.count() == 2
    assert xtdb_org1 not in network.organizations.all()
    assert xtdb_org2 in network.organizations.all()
    assert xtdb_org3 in network.organizations.all()


def test_network_manage_organizations_remove_all(rf, superuser_member, xtdb):
    """Test removing all organizations from a network."""
    org = Organization.objects.create(name="Test Org")
    xtdb_org = XTDBOrganization.objects.get(pk=org.pk)
    network = Network.objects.create(name="test-network")
    network.organizations.add(xtdb_org)

    request = setup_request(
        rf.post("objects:network_manage_organizations", {"organizations": []}), superuser_member.user
    )
    response = NetworkManageOrganizationsView.as_view()(request, pk=network.pk)

    assert response.status_code == 302
    assert network.organizations.count() == 0

    messages = list(request._messages)
    assert any("All organizations removed" in str(m) for m in messages)


def test_ipaddress_manage_organizations_add(rf, superuser_member, xtdb):
    """Test adding organizations to an IP address."""
    org1 = Organization.objects.create(name="Org 1")
    org2 = Organization.objects.create(name="Org 2")
    xtdb_org1 = XTDBOrganization.objects.get(pk=org1.pk)
    xtdb_org2 = XTDBOrganization.objects.get(pk=org2.pk)
    network = Network.objects.create(name="internet")
    ip = IPAddress.objects.create(ip_address="192.168.1.1", network=network)

    request = setup_request(
        rf.post("objects:ipaddress_manage_organizations", {"organizations": [org1.pk, org2.pk]}), superuser_member.user
    )
    response = IPAddressManageOrganizationsView.as_view()(request, pk=ip.pk)

    assert response.status_code == 302
    assert ip.organizations.count() == 2
    assert xtdb_org1 in ip.organizations.all()
    assert xtdb_org2 in ip.organizations.all()

    messages = list(request._messages)
    assert any("Organizations updated successfully" in str(m) for m in messages)


def test_ipaddress_manage_organizations_update(rf, superuser_member, xtdb):
    """Test updating organizations on an IP address."""
    org1 = Organization.objects.create(name="Org 1")
    org2 = Organization.objects.create(name="Org 2")
    xtdb_org1 = XTDBOrganization.objects.get(pk=org1.pk)
    xtdb_org2 = XTDBOrganization.objects.get(pk=org2.pk)
    network = Network.objects.create(name="internet")
    ip = IPAddress.objects.create(ip_address="192.168.1.1", network=network)
    ip.organizations.add(xtdb_org1)

    request = setup_request(
        rf.post("objects:ipaddress_manage_organizations", {"organizations": [org2.pk]}), superuser_member.user
    )
    response = IPAddressManageOrganizationsView.as_view()(request, pk=ip.pk)

    assert response.status_code == 302
    assert ip.organizations.count() == 1
    assert xtdb_org1 not in ip.organizations.all()
    assert xtdb_org2 in ip.organizations.all()


def test_hostname_manage_organizations_add(rf, superuser_member, xtdb):
    """Test adding organizations to a hostname."""
    org1 = Organization.objects.create(name="Org 1")
    org2 = Organization.objects.create(name="Org 2")
    xtdb_org1 = XTDBOrganization.objects.get(pk=org1.pk)
    xtdb_org2 = XTDBOrganization.objects.get(pk=org2.pk)
    network = Network.objects.create(name="internet")
    host = Hostname.objects.create(name="example.com", network=network)

    request = setup_request(
        rf.post("objects:hostname_manage_organizations", {"organizations": [org1.pk, org2.pk]}), superuser_member.user
    )
    response = HostnameManageOrganizationsView.as_view()(request, pk=host.pk)

    assert response.status_code == 302
    assert host.organizations.count() == 2
    assert xtdb_org1 in host.organizations.all()
    assert xtdb_org2 in host.organizations.all()

    messages = list(request._messages)
    assert any("Organizations updated successfully" in str(m) for m in messages)


def test_hostname_manage_organizations_remove_all(rf, superuser_member, xtdb):
    """Test removing all organizations from a hostname."""
    org = Organization.objects.create(name="Test Org")
    xtdb_org = XTDBOrganization.objects.get(pk=org.pk)
    network = Network.objects.create(name="internet")
    host = Hostname.objects.create(name="example.com", network=network)
    host.organizations.add(xtdb_org)

    request = setup_request(
        rf.post("objects:hostname_manage_organizations", {"organizations": []}), superuser_member.user
    )
    response = HostnameManageOrganizationsView.as_view()(request, pk=host.pk)

    assert response.status_code == 302
    assert host.organizations.count() == 0

    messages = list(request._messages)
    assert any("All organizations removed" in str(m) for m in messages)


# Edge Case Tests


def test_csv_upload_with_empty_organization_column(rf, superuser_member, xtdb):
    """Test CSV upload with empty organization column (should be treated as no org)."""
    csv_content = b"192.168.1.1,\n10.0.0.1,"
    csv_file = BytesIO(csv_content)
    csv_file.name = "ip_addresses.csv"

    request = setup_request(rf.post("objects:ipaddress_csv_upload", {"csv_file": csv_file}), superuser_member.user)
    response = IPAddressCSVUploadView.as_view()(request)

    assert response.status_code == 302
    assert IPAddress.objects.count() == 2

    # Check that no organizations were assigned
    ip1 = IPAddress.objects.get(ip_address="192.168.1.1")
    ip2 = IPAddress.objects.get(ip_address="10.0.0.1")
    assert ip1.organizations.count() == 0
    assert ip2.organizations.count() == 0


def test_csv_upload_with_whitespace_organization_id(rf, superuser_member, xtdb):
    """Test CSV upload with whitespace-only organization id."""
    csv_content = b"192.168.1.1,   "
    csv_file = BytesIO(csv_content)
    csv_file.name = "ip_addresses.csv"

    request = setup_request(rf.post("objects:ipaddress_csv_upload", {"csv_file": csv_file}), superuser_member.user)
    response = IPAddressCSVUploadView.as_view()(request)

    assert response.status_code == 302
    assert IPAddress.objects.count() == 1

    # Check that no organizations were assigned
    ip = IPAddress.objects.get(ip_address="192.168.1.1")
    assert ip.organizations.count() == 0


def test_multiple_organizations_not_supported_in_csv(rf, superuser_member, xtdb):
    """Test that CSV format doesn't support multiple organizations (only one org per row)."""
    org1 = Organization.objects.create(name="Org 1")
    org2 = Organization.objects.create(name="Org 2")
    xtdb_org1 = XTDBOrganization.objects.get(pk=org1.pk)
    xtdb_org2 = XTDBOrganization.objects.get(pk=org2.pk)
    csv_content = b"192.168.1.1," + str(xtdb_org1.id).encode()  # Only one org code supported
    csv_file = BytesIO(csv_content)
    csv_file.name = "ip_addresses.csv"

    request = setup_request(rf.post("objects:ipaddress_csv_upload", {"csv_file": csv_file}), superuser_member.user)
    response = IPAddressCSVUploadView.as_view()(request)

    assert response.status_code == 302
    ip = IPAddress.objects.get(ip_address="192.168.1.1")
    assert ip.organizations.count() == 1
    assert xtdb_org1 in ip.organizations.all()
    assert xtdb_org2 not in ip.organizations.all()
