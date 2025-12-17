from objects.models import (
    DNSAAAARecord,
    DNSARecord,
    DNSCNAMERecord,
    DNSNSRecord,
    Finding,
    FindingType,
    Hostname,
    IPAddress,
    Network,
    XTDBOrganization,
)
from tasks.tasks import attribute_findings, organization_attribution


def test_organization_attribution_through_a_records(xtdb, organization):
    network = Network.objects.create(name="internet")
    hostname = Hostname.objects.create(network=network, name="test.com")
    hostname.organizations.add(organization.pk)
    ip = IPAddress.objects.create(network=network, ip_address="192.168.1.1")
    DNSARecord.objects.create(hostname=hostname, ip_address=ip)

    assert ip.organizations.count() == 0

    organization_attribution()

    ip.refresh_from_db()
    assert ip.organizations.count() == 1
    assert organization.pk in [org.pk for org in ip.organizations.all()]


def test_organization_attribution_through_aaaa_records(xtdb, organization):
    network = Network.objects.create(name="internet")
    hostname = Hostname.objects.create(network=network, name="test.com")
    hostname.organizations.add(organization.pk)

    ipv6 = IPAddress.objects.create(network=network, ip_address="2001:db8::1")

    DNSAAAARecord.objects.create(hostname=hostname, ip_address=ipv6)

    assert ipv6.organizations.count() == 0

    organization_attribution()

    ipv6.refresh_from_db()
    assert ipv6.organizations.count() == 1
    assert organization.pk in [org.pk for org in ipv6.organizations.all()]


def test_organization_attribution_from_ip_to_hostname(xtdb, organization):
    network = Network.objects.create(name="internet")

    ip = IPAddress.objects.create(network=network, ip_address="192.168.1.1")
    ip.organizations.add(organization.pk)

    hostname = Hostname.objects.create(network=network, name="test.com")

    DNSARecord.objects.create(hostname=hostname, ip_address=ip)

    assert hostname.organizations.count() == 0

    organization_attribution()

    hostname.refresh_from_db()
    assert hostname.organizations.count() == 1
    assert organization.pk in [org.pk for org in hostname.organizations.all()]


def test_organization_attribution_through_cname(xtdb, organization):
    network = Network.objects.create(name="internet")

    target = Hostname.objects.create(network=network, name="target.com")
    target.organizations.add(organization.pk)
    source = Hostname.objects.create(network=network, name="source.com")

    DNSCNAMERecord.objects.create(hostname=source, target=target)

    assert source.organizations.count() == 0

    organization_attribution()

    source.refresh_from_db()
    assert source.organizations.count() == 1
    assert organization.pk in [org.pk for org in source.organizations.all()]


def test_organization_attribution_through_ns_records(xtdb, organization):
    network = Network.objects.create(name="internet")

    hostname = Hostname.objects.create(network=network, name="example.com")
    hostname.organizations.add(organization.pk)

    nameserver = Hostname.objects.create(network=network, name="ns1.example.com")

    DNSNSRecord.objects.create(hostname=hostname, name_server=nameserver)

    assert nameserver.organizations.count() == 0

    organization_attribution()

    nameserver.refresh_from_db()
    assert nameserver.organizations.count() == 1
    assert organization.pk in [org.pk for org in nameserver.organizations.all()]


def test_organization_attribution_does_not_duplicate(xtdb, organization):
    network = Network.objects.create(name="internet")

    hostname = Hostname.objects.create(network=network, name="test.com")
    hostname.organizations.add(organization.pk)

    ip = IPAddress.objects.create(network=network, ip_address="192.168.1.1")

    DNSARecord.objects.create(hostname=hostname, ip_address=ip)

    organization_attribution()
    organization_attribution()

    ip.refresh_from_db()
    assert ip.organizations.count() == 1
    assert organization.pk in [org.pk for org in ip.organizations.all()]


def test_organization_attribution_multiple_organizations(xtdb, organization, organization_b):
    network = Network.objects.create(name="internet")

    hostname1 = Hostname.objects.create(network=network, name="test1.com")
    hostname1.organizations.add(organization.pk)

    hostname2 = Hostname.objects.create(network=network, name="test2.com")
    hostname2.organizations.add(XTDBOrganization.objects.get(pk=organization_b.pk))

    ip = IPAddress.objects.create(network=network, ip_address="192.168.1.1")

    DNSARecord.objects.create(hostname=hostname1, ip_address=ip)
    DNSARecord.objects.create(hostname=hostname2, ip_address=ip)

    organization_attribution()

    ip.refresh_from_db()
    assert ip.organizations.count() == 2
    org_pks = {org.pk for org in ip.organizations.all()}
    assert organization.pk in org_pks
    assert organization_b.pk in org_pks


def test_organization_attribution_multiple_organizations_later(xtdb, organization, organization_b):
    network = Network.objects.create(name="internet")

    hostname1 = Hostname.objects.create(network=network, name="test1.com")
    hostname1.organizations.add(organization.pk)

    hostname2 = Hostname.objects.create(network=network, name="test2.com")

    ip = IPAddress.objects.create(network=network, ip_address="192.168.1.1")

    DNSARecord.objects.create(hostname=hostname1, ip_address=ip)
    DNSARecord.objects.create(hostname=hostname2, ip_address=ip)

    organization_attribution()

    ip.refresh_from_db()
    assert ip.organizations.count() == 1
    org_pks = {org.pk for org in ip.organizations.all()}
    assert organization.pk in org_pks

    hostname2.organizations.add(XTDBOrganization.objects.get(pk=organization_b.pk))

    organization_attribution()

    ip.refresh_from_db()
    assert ip.organizations.count() == 2
    org_pks = {org.pk for org in ip.organizations.all()}
    assert organization.pk in org_pks
    assert organization_b.pk in org_pks


def test_organization_attribution_chain(xtdb, organization):
    network = Network.objects.create(name="internet")
    hostname1 = Hostname.objects.create(network=network, name="test1.com")
    hostname1.organizations.add(organization.pk)

    ip = IPAddress.objects.create(network=network, ip_address="192.168.1.1")
    hostname2 = Hostname.objects.create(network=network, name="test2.com")

    DNSARecord.objects.create(hostname=hostname1, ip_address=ip)
    DNSARecord.objects.create(hostname=hostname2, ip_address=ip)

    organization_attribution()

    ip.refresh_from_db()
    hostname2.refresh_from_db()

    assert ip.organizations.count() == 1
    assert hostname2.organizations.count() == 1
    assert organization.pk in [org.pk for org in ip.organizations.all()]
    assert organization.pk in [org.pk for org in hostname2.organizations.all()]


def test_attribute_findings_from_hostname(xtdb, organization):
    network = Network.objects.create(name="internet")
    hostname = Hostname.objects.create(network=network, name="test.com")
    hostname.organizations.add(organization.pk)

    finding_type = FindingType.objects.create(code="TEST-FINDING")
    finding = Finding.objects.create(hostname=hostname, finding_type=finding_type)

    assert finding.organizations.count() == 0

    attribute_findings()

    finding.refresh_from_db()
    assert finding.organizations.count() == 1
    assert organization.pk in [org.pk for org in finding.organizations.all()]


def test_attribute_findings_from_ipaddress(xtdb, organization):
    network = Network.objects.create(name="internet")
    ip = IPAddress.objects.create(network=network, ip_address="192.168.1.1")
    ip.organizations.add(organization.pk)

    finding_type = FindingType.objects.create(code="TEST-FINDING")
    finding = Finding.objects.create(ip_address=ip, finding_type=finding_type)

    assert finding.organizations.count() == 0

    attribute_findings()

    finding.refresh_from_db()
    assert finding.organizations.count() == 1
    assert organization.pk in [org.pk for org in finding.organizations.all()]


def test_attribute_findings_multiple_organizations(xtdb, organization, organization_b):
    network = Network.objects.create(name="internet")
    hostname = Hostname.objects.create(network=network, name="test.com")
    hostname.organizations.add(organization.pk)
    hostname.organizations.add(organization_b.pk)

    finding_type = FindingType.objects.create(code="TEST-FINDING")
    finding = Finding.objects.create(hostname=hostname, finding_type=finding_type)

    attribute_findings()

    finding.refresh_from_db()
    assert finding.organizations.count() == 2
    org_pks = {org.pk for org in finding.organizations.all()}
    assert organization.pk in org_pks
    assert organization_b.pk in org_pks


def test_attribute_findings_does_not_duplicate(xtdb, organization):
    network = Network.objects.create(name="internet")
    hostname = Hostname.objects.create(network=network, name="test.com")
    hostname.organizations.add(organization.pk)

    finding_type = FindingType.objects.create(code="TEST-FINDING")
    finding = Finding.objects.create(hostname=hostname, finding_type=finding_type)

    attribute_findings()
    attribute_findings()

    finding.refresh_from_db()
    assert finding.organizations.count() == 1
    assert organization.pk in [org.pk for org in finding.organizations.all()]
