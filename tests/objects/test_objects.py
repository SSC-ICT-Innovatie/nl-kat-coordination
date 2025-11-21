import pytest
from django.core.exceptions import ValidationError
from pytest_django.asserts import assertContains, assertNotContains

from objects.management.commands.generate_benchmark_data import generate
from objects.models import (
    DNSAAAARecord,
    DNSARecord,
    DNSNSRecord,
    Finding,
    FindingType,
    Hostname,
    HostnameOrganization,
    IPAddress,
    IPPort,
    Network,
    Protocol,
    Software,
    XTDBOrganization,
    bulk_insert,
    to_xtdb_dict,
)
from objects.views import FindingListView, HostnameCreateView, IPAddressCreateView, NetworkCreateView, NetworkListView
from tasks.tasks import recalculate_scan_levels, sync_ns_scan_levels
from tests.conftest import setup_request


def test_query_hostname(xtdb, organization):
    network = Network.objects.create(name="internet")
    Hostname.objects.create(network=network, name="test.com")

    networks = Network.objects.filter(hostname__name="test.com")
    assert networks.count() == 1
    networks = Network.objects.filter(hostname__name="none.com")
    assert networks.count() == 0

    network.organizations.add(XTDBOrganization.objects.get(pk=organization.pk))
    network.save()
    assert Network.objects.filter(organizations__in=[]).count() == 0
    assert Network.objects.filter(organizations__pk__in=[organization.pk]).count() == 1


def test_recalculate_scan_levels_hostname_ip(xtdb, organization):
    network = Network.objects.create(name="internet")

    h = Hostname.objects.create(network=network, name="test.com", scan_level=2)
    # The A record inherits level 2 from the hostname test.com
    ip = IPAddress.objects.create(network=network, address="0.0.0.0", scan_level=1)
    DNSARecord.objects.create(ip_address=ip, hostname=h)

    # The AAAA record inherits level 2 from the hostname test.com
    ip6 = IPAddress.objects.create(network=network, address="0.0.0.0")
    DNSAAAARecord.objects.create(ip_address=ip6, hostname=h)

    ip2 = IPAddress.objects.create(network=network, address="1.0.0.0")
    DNSARecord.objects.create(ip_address=ip2, hostname=h)

    recalculate_scan_levels()

    ip.refresh_from_db()
    assert ip.scan_level == 2

    ip.scan_level = 3
    ip.save()
    recalculate_scan_levels()

    h.refresh_from_db()
    assert h.scan_level == 3


def test_recalculate_scan_levels_nameserver(xtdb, organization):
    network = Network.objects.create(name="internet")
    h = Hostname.objects.create(network=network, name="test.com", scan_level=2)

    nameserver = Hostname.objects.create(network=network, name="ns.test.com")
    DNSNSRecord.objects.create(name_server=nameserver, hostname=h)

    sync_ns_scan_levels()

    nameserver.refresh_from_db()
    assert nameserver.scan_level == 1


def test_recalculate_scan_levels_does_not_change_declared(xtdb, organization):
    network = Network.objects.create(name="internet")

    h = Hostname.objects.create(network=network, name="test.com", scan_level=2)
    ip = IPAddress.objects.create(network=network, address="0.0.0.0", scan_level=1, declared=True)
    DNSARecord.objects.create(ip_address=ip, hostname=h)
    nameserver = Hostname.objects.create(network=network, name="ns.test.com", scan_level=2, declared=True)
    DNSNSRecord.objects.create(name_server=nameserver, hostname=h)

    recalculate_scan_levels()

    ip.refresh_from_db()
    assert ip.scan_level == 1

    nameserver.refresh_from_db()
    assert nameserver.scan_level == 2


def test_recalculate_scan_levels_creates_new_profiles(xtdb, organization):
    network = Network.objects.create(name="internet")

    h = Hostname.objects.create(network=network, name="test.com", scan_level=2)
    ip = IPAddress.objects.create(network=network, address="0.0.0.0")
    DNSARecord.objects.create(ip_address=ip, hostname=h)

    recalculate_scan_levels()

    ip.refresh_from_db()
    assert ip.scan_level == 2
    assert ip.declared is False

    h.refresh_from_db()
    assert h.scan_level == 2
    assert h.declared is False


def test_network_view_filtered_on_name(rf, superuser_member, xtdb):
    Network.objects.create(name="internet")

    request = setup_request(rf.get("objects:network_list", query_params={"name": "nter"}), superuser_member.user)
    response = NetworkListView.as_view()(request)
    assert response.status_code == 200
    assertContains(response, "internet")
    assertContains(response, "Networks")

    request = setup_request(rf.get("objects:network_list"), superuser_member.user)
    response = NetworkListView.as_view()(request)
    assert response.status_code == 200
    assertContains(response, "internet")

    request = setup_request(rf.get("objects:network_list", query_params={"name": "no"}), superuser_member.user)
    response = NetworkListView.as_view()(request)
    assert response.status_code == 200
    assertNotContains(response, "internet")


def test_findings(rf, superuser_member, xtdb):
    net = Network.objects.create(name="internet")
    host = Hostname.objects.create(name="test.com", network=net)
    finding_type = FindingType.objects.create(code="KAT-TEST-LIST-VIEW", score=3.1)
    Finding.objects.create(hostname=host, finding_type=finding_type)

    request = setup_request(rf.get("objects:finding_list"), superuser_member.user)
    response = FindingListView.as_view()(request)
    assert response.status_code == 200
    assertContains(response, "Severity")
    assertContains(response, "Object")
    assertContains(response, "test.com")
    assertContains(response, "3.1")

    request = setup_request(
        rf.get("objects:finding_list", query_params={"object_search": "mail"}), superuser_member.user
    )
    response = FindingListView.as_view()(request)
    assertNotContains(response, "test.com")

    request = setup_request(
        rf.get("objects:finding_list", query_params={"finding_type__score__gte": 5}), superuser_member.user
    )
    response = FindingListView.as_view()(request)
    assertNotContains(response, "test.com")

    request = setup_request(
        rf.get("objects:finding_list", query_params={"finding_type__score__gte": 3}), superuser_member.user
    )
    response = FindingListView.as_view()(request)
    assertContains(response, "test.com")

    request = setup_request(
        rf.get("objects:finding_list", query_params={"finding_type__code": "KAT-WRONG"}), superuser_member.user
    )
    response = FindingListView.as_view()(request)
    assertNotContains(response, "test.com")

    request = setup_request(
        rf.get("objects:finding_list", query_params={"finding_type__code": "KAT-TEST-LIST-VIEW"}), superuser_member.user
    )
    response = FindingListView.as_view()(request)
    assertContains(response, "test.com")

    request = setup_request(
        rf.get("objects:finding_list", query_params={"object_search": "test"}), superuser_member.user
    )
    response = FindingListView.as_view()(request)
    assertContains(response, "test.com")

    host.delete()
    assert Finding.objects.count() == 0


def test_update_get_or_create(xtdb):
    net = Network.objects.create(name="internet")
    assert Network.objects.count() == 1

    Network.objects.create(name="internet")
    assert Network.objects.count() == 1

    Network.objects.create(name="internet")
    assert Network.objects.count() == 1

    other, created = Network.objects.get_or_create(name="internet")
    assert net == other

    other, created = Network.objects.get_or_create(name="test")
    assert net != other


def test_bulk_create(xtdb):
    net = Network(name="internet")
    net2 = Network(name="internet2")
    net3 = Network(name="internet3")
    Network.objects.bulk_create([net, net2, net3])

    assert Network.objects.count() == 3

    nnet = Network(name="internet2")
    nnet2 = Network(name="internet2")
    nnet3 = Network(name="internet4")
    Network.objects.bulk_create([nnet, nnet2, nnet3], unique_fields=["name"])

    assert Network.objects.count() == 4


def test_bulk_insert_networks(xtdb):
    net = Network(name="internet")
    net2 = Network(name="internet2")
    net3 = Network(name="internet3")

    bulk_insert([net, net2, net3])
    assert Network.objects.count() == 3

    net4 = Network(name="internet4")
    net5 = Network(name="internet5")
    net6 = Network(name="internet6")
    host = Hostname(name="test.com", network=net)
    bulk_insert([net4, net5, net6, host])

    assert Network.objects.count() == 6
    assert Hostname.objects.count() == 0


def test_to_dict(xtdb):
    net = Network.objects.create(name="internet")
    host = Hostname.objects.create(name="test.com", network=net)
    ip = IPAddress.objects.create(network=net, address="2001:ab8:d0cb::")
    rec = DNSARecord.objects.create(hostname=host, ip_address=ip)
    port = IPPort.objects.create(address=ip, protocol=Protocol.TCP, port=22, tls=False, service="ssh")
    sw = Software.objects.create(name="openssh")
    port.software.add(sw)
    port.save()
    assert to_xtdb_dict(net) == {"name": "internet", "_id": net.pk, "declared": False, "scan_level": None}
    assert to_xtdb_dict(host) == {
        "name": "test.com",
        "network_id": net.pk,
        "_id": host.id,
        "root": True,
        "declared": False,
        "scan_level": None,
    }
    assert to_xtdb_dict(sw) == {"_id": sw.id, "cpe": None, "name": "openssh", "version": None}
    assert to_xtdb_dict(rec) == {
        "_id": "internet|test.com|internet|2001:ab8:d0cb::",
        "hostname_id": "internet|test.com",
        "ip_address_id": "internet|2001:ab8:d0cb::",
        "ttl": None,
    }

    h = Hostname(name="test2.com", network=net)
    assert to_xtdb_dict(h) == {
        "name": "test2.com",
        "network_id": net.pk,
        "_id": "internet|test2.com",
        "root": False,  # changed upon save
        "declared": False,
        "scan_level": None,
    }
    ip = IPAddress(network=net, address="2002:ab8:d0cb::")
    rec = DNSARecord(hostname=h, ip_address=ip)
    assert to_xtdb_dict(rec) == {
        "_id": "internet|test2.com|internet|2002:ab8:d0cb::",
        "hostname_id": "internet|test2.com",
        "ip_address_id": "internet|2002:ab8:d0cb::",
        "ttl": None,
    }


def test_bulk_insert_hostnames(xtdb, organization):
    net = Network.objects.create(name="internet")
    host = Hostname.objects.create(name="test.com", network=net)
    host1 = Hostname.objects.create(name="test1.com", network=net)
    host2 = Hostname.objects.create(name="test2.com", network=net)
    host3 = Hostname.objects.create(name="test3.com", network=net)

    bulk_insert([host, host1, host2, host3])
    assert Hostname.objects.count() == 4

    host4 = Hostname.objects.create(name="test4.com", network=net)
    bulk_insert([host4])
    assert Hostname.objects.count() == 5

    HostnameOrganization.objects.bulk_create([HostnameOrganization(hostname=host4, organization_id=organization.pk)])
    assert HostnameOrganization.objects.count() == 1


def test_generate_benchmark_data(xtdb):
    objects = generate(10, 1, 1, True)
    for object_t in objects:
        bulk_insert(object_t)

    assert Network.objects.count() == 1
    assert Hostname.objects.count() == 10
    assert IPAddress.objects.count() == 12
    assert DNSARecord.objects.count() == 5
    assert Software.objects.count() == 2


def test_from_natural_key():
    h = Hostname.from_natural_key("test|test.com")
    assert h.name == "test.com"

    with pytest.raises(ValueError):
        Hostname.from_natural_key("test|test.com|2")

    ip = IPAddress.from_natural_key("test|127.0.0.1")
    assert ip.address == "127.0.0.1"

    with pytest.raises(ValueError):
        IPAddress.from_natural_key("127.0.0.1")

    a = DNSARecord.from_natural_key("test|test.com|test|127.0.0.1")
    assert a.hostname.name == "test.com"
    assert a.ip_address.address == "127.0.0.1"

    with pytest.raises(ValueError):
        DNSARecord.from_natural_key("test|test.com|127.0.0.1")


def test_network_create_view_get(rf, superuser_member, xtdb):
    request = setup_request(rf.get("objects:network_create"), superuser_member.user)
    response = NetworkCreateView.as_view()(request)
    assert response.status_code == 200
    assertContains(response, "Add Object")
    assertContains(response, "Name:")


def test_network_create_view_post_success(rf, superuser_member, xtdb):
    assert Network.objects.count() == 0

    request = setup_request(
        rf.post(
            "objects:network_create", data={"name": "test-network", "organizations": [superuser_member.organization.pk]}
        ),
        superuser_member.user,
    )
    response = NetworkCreateView.as_view()(request)

    assert response.status_code == 302
    assert response.url == "/en/objects/network/"

    assert Network.objects.count() == 1
    network = Network.objects.first()
    assert network.name == "test-network"
    assert network.declared is False
    assert network.scan_level is None


def test_network_create_view_post_duplicate_fails(rf, superuser_member, xtdb):
    Network.objects.create(name="existing-network")

    request = setup_request(rf.post("objects:network_create", data={"name": "existing-network"}), superuser_member.user)
    response = NetworkCreateView.as_view()(request)

    assert response.status_code == 200
    assertContains(response, "Network with this Name already exists")

    assert Network.objects.count() == 1


def test_network_create_view_post_missing_name_fails(rf, superuser_member, xtdb):
    request = setup_request(rf.post("objects:network_create", data={}), superuser_member.user)
    response = NetworkCreateView.as_view()(request)

    assert response.status_code == 200
    assertContains(response, "This field is required")

    assert Network.objects.count() == 0


def test_hostname_create_view_get(rf, superuser_member, xtdb):
    request = setup_request(rf.get("objects:hostname_create"), superuser_member.user)
    response = HostnameCreateView.as_view()(request)
    assert response.status_code == 200
    assertContains(response, "Add Hostname")
    assertContains(response, "Network:")
    assertContains(response, "Name:")


def test_hostname_create_view_get_with_internet_network(rf, superuser_member, xtdb):
    Network.objects.create(name="internet")

    request = setup_request(rf.get("objects:hostname_create"), superuser_member.user)
    response = HostnameCreateView.as_view()(request)
    assert response.status_code == 200

    assertContains(response, "selected")
    assertContains(response, "internet")


def test_hostname_create_view_post_success(rf, superuser_member, xtdb):
    network = Network.objects.create(name="test-network")
    assert Hostname.objects.count() == 0

    request = setup_request(
        rf.post(
            "objects:hostname_create",
            data={"network": network.pk, "name": "example.com", "organizations": [superuser_member.organization.pk]},
        ),
        superuser_member.user,
    )
    response = HostnameCreateView.as_view()(request)

    assert response.status_code == 302
    assert response.url == "/en/objects/hostname/"

    assert Hostname.objects.count() == 1
    hostname = Hostname.objects.first()
    assert hostname.name == "example.com"
    assert hostname.network == network
    assert hostname.declared is False
    assert hostname.scan_level is None


def test_hostname_create_view_post_duplicate_is_idempotent(rf, superuser_member, xtdb):
    network = Network.objects.create(name="test-network")
    Hostname.objects.create(network=network, name="existing.com")

    request = setup_request(
        rf.post(
            "objects:hostname_create",
            data={"network": network.pk, "name": "existing.com", "organizations": [superuser_member.organization.pk]},
        ),
        superuser_member.user,
    )
    response = HostnameCreateView.as_view()(request)

    assert response.status_code == 302
    assert Hostname.objects.count() == 1


def test_hostname_create_view_post_missing_fields_fails(rf, superuser_member, xtdb):
    request = setup_request(rf.post("objects:hostname_create", data={}), superuser_member.user)
    response = HostnameCreateView.as_view()(request)

    assert response.status_code == 200
    assertContains(response, "This field is required")
    assert Hostname.objects.count() == 0


def test_hostname_create_view_post_subdomain(rf, superuser_member, xtdb):
    network = Network.objects.create(name="internet")
    parent = Hostname.objects.create(network=network, name="example.com")
    request = setup_request(
        rf.post(
            "objects:hostname_create",
            data={
                "network": network.pk,
                "name": "sub.example.com",
                "organizations": [superuser_member.organization.pk],
            },
        ),
        superuser_member.user,
    )
    HostnameCreateView.as_view()(request)

    assert Hostname.objects.count() == 2

    parent.refresh_from_db()
    subdomain = Hostname.objects.get(name="sub.example.com")

    assert parent.root is True
    assert subdomain.root is False


def test_ipaddress_create_view_get(rf, superuser_member, xtdb):
    request = setup_request(rf.get("objects:ipaddress_create"), superuser_member.user)
    response = IPAddressCreateView.as_view()(request)
    assert response.status_code == 200
    assertContains(response, "Add IP Address")
    assertContains(response, "Network:")
    assertContains(response, "Address:")


def test_ipaddress_create_view_get_with_internet_network(rf, superuser_member, xtdb):
    Network.objects.create(name="internet")

    request = setup_request(rf.get("objects:ipaddress_create"), superuser_member.user)
    response = IPAddressCreateView.as_view()(request)
    assert response.status_code == 200

    assertContains(response, "selected")
    assertContains(response, "internet")


def test_ipaddress_create_view_post_ipv4_success(rf, superuser_member, xtdb):
    network = Network.objects.create(name="test-network")
    assert IPAddress.objects.count() == 0

    request = setup_request(
        rf.post(
            "objects:ipaddress_create",
            data={"network": network.pk, "address": "192.0.2.1", "organizations": [superuser_member.organization.pk]},
        ),
        superuser_member.user,
    )
    response = IPAddressCreateView.as_view()(request)

    assert response.status_code == 302
    assert response.url == "/en/objects/ipaddress/"

    assert IPAddress.objects.count() == 1
    ip = IPAddress.objects.first()
    assert ip.address == "192.0.2.1"
    assert ip.network == network
    assert ip.declared is False
    assert ip.scan_level is None


def test_ipaddress_create_view_post_ipv6_success(rf, superuser_member, xtdb):
    network = Network.objects.create(name="test-network")
    request = setup_request(
        rf.post(
            "objects:ipaddress_create",
            data={"network": network.pk, "address": "2001:db8::1", "organizations": [superuser_member.organization.pk]},
        ),
        superuser_member.user,
    )
    response = IPAddressCreateView.as_view()(request)

    assert response.status_code == 302

    assert IPAddress.objects.count() == 1
    ip = IPAddress.objects.first()
    assert ip.address == "2001:db8::1"


def test_ipaddress_create_view_post_duplicate_is_idempotent(rf, superuser_member, xtdb):
    network = Network.objects.create(name="test-network")
    IPAddress.objects.create(network=network, address="192.0.2.50")

    request = setup_request(
        rf.post(
            "objects:ipaddress_create",
            data={"network": network.pk, "address": "192.0.2.50", "organizations": [superuser_member.organization.pk]},
        ),
        superuser_member.user,
    )
    response = IPAddressCreateView.as_view()(request)
    assert response.status_code == 302
    assert IPAddress.objects.count() == 1


def test_ipaddress_create_view_post_missing_fields_fails(rf, superuser_member, xtdb):
    request = setup_request(rf.post("objects:ipaddress_create", data={}), superuser_member.user)
    response = IPAddressCreateView.as_view()(request)

    assert response.status_code == 200
    assertContains(response, "This field is required")

    assert IPAddress.objects.count() == 0


def test_ipaddress_create_view_post_invalid_ip_fails(rf, superuser_member, xtdb):
    network = Network.objects.create(name="test-network")

    request = setup_request(
        rf.post("objects:ipaddress_create", data={"network": network.pk, "address": "not-an-ip"}), superuser_member.user
    )
    response = IPAddressCreateView.as_view()(request)

    assert response.status_code == 200
    assertContains(response, "Enter a valid")
    assert IPAddress.objects.count() == 0


def test_hostname_validation_valid_hostnames(xtdb, organization):
    """Test that valid hostnames pass validation."""
    network = Network.objects.create(name="internet")

    # Valid subdomain
    h3 = Hostname.objects.create(network=network, name="sub.example.com")
    assert h3.name == "sub.example.com"


def test_hostname_validation_trailing_dot_normalization(xtdb, organization):
    """Test that single trailing dot is normalized (FQDN notation)."""
    network = Network.objects.create(name="internet")

    # Hostname with single trailing dot should be normalized
    h1 = Hostname.objects.create(network=network, name="example.com.")
    assert h1.name == "example.com"

    # Multiple trailing dots should raise ValidationError
    with pytest.raises(ValidationError, match="empty labels"):
        Hostname.objects.create(network=network, name="test.example.com...")


def test_hostname_validation_empty_hostname(xtdb, organization):
    """Test that empty hostname raises error."""
    network = Network.objects.create(name="internet")

    # Empty hostname will raise ValueError from natural key validation
    # (which happens before our hostname validation)
    with pytest.raises(ValueError, match="natural key attributes must be set"):
        Hostname.objects.create(network=network, name="")


def test_hostname_validation_when_creating_object(xtdb, organization):
    """Test that labels starting or ending with hyphens raise ValidationError."""
    network = Network.objects.create(name="internet")

    # Label starting with hyphen
    with pytest.raises(ValidationError, match="cannot start or end with a hyphen"):
        Hostname.objects.create(network=network, name="-example.com")

    # Underscore
    with pytest.raises(ValidationError, match="invalid characters"):
        Hostname.objects.create(network=network, name="example_test.com")


def test_hostname_validation_case_insensitive(xtdb, organization):
    """Test that hostnames are case-insensitive (lowercased by LowerCaseCharField)."""
    network = Network.objects.create(name="internet")

    # Mixed case should be converted to lowercase
    h = Hostname.objects.create(network=network, name="Example.COM")
    assert h.name == "example.com"


def test_hostname_validation_with_bulk_create(xtdb, organization):
    """Test that validation works with bulk_create (which calls save() on each object)."""
    network = Network.objects.create(name="internet")

    # Valid hostnames should work with bulk_create
    valid_hostnames = [
        Hostname(network=network, name="example1.com"),
        Hostname(network=network, name="example2.com"),
        Hostname(network=network, name="sub.example3.com"),
    ]
    Hostname.objects.bulk_create(valid_hostnames)
    # Verify the hostnames were created
    assert Hostname.objects.filter(network=network, name="example1.com").exists()
    assert Hostname.objects.filter(network=network, name="example2.com").exists()
    assert Hostname.objects.filter(network=network, name="sub.example3.com").exists()

    # Invalid hostname should raise ValidationError during bulk_create
    invalid_hostnames = [
        Hostname(network=network, name="valid.com"),
        Hostname(network=network, name="invalid_hostname.com"),  # underscore is invalid
    ]
    with pytest.raises(ValidationError, match="invalid characters"):
        Hostname.objects.bulk_create(invalid_hostnames)

    # Trailing dot normalization should work with bulk_create
    hostnames_with_dot = [Hostname(network=network, name="test1.com."), Hostname(network=network, name="test2.com.")]
    Hostname.objects.bulk_create(hostnames_with_dot)
    # Verify trailing dots were normalized
    h1 = Hostname.objects.get(network=network, name="test1.com")
    h2 = Hostname.objects.get(network=network, name="test2.com")
    assert h1.name == "test1.com"
    assert h2.name == "test2.com"
