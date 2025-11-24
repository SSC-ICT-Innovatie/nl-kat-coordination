from django.db import connections

from objects.models import (
    CAATag,
    DNSAAAARecord,
    DNSCAARecord,
    DNSMXRecord,
    DNSNSRecord,
    DNSTXTRecord,
    Finding,
    FindingType,
    Hostname,
    IPAddress,
    IPPort,
    Network,
    Protocol,
)
from plugins.plugins.business_rules import get_rules


def test_ipv6_query(xtdb):
    network = Network.objects.create(name="test")
    hn = Hostname.objects.create(network=network, name="test.com")
    ns = Hostname.objects.create(network=network, name="ns1.test.com")
    DNSNSRecord.objects.create(hostname=hn, name_server=ns)

    hns = Hostname.objects.raw(get_rules()["ipv6_webservers"]["query"])
    assert len(hns) == 1
    assert hns[0].name == "test.com"

    ip = IPAddress.objects.create(network=network, address="2001:ab8:d0cb::")
    DNSAAAARecord.objects.create(hostname=hn, ip_address=ip)  # Add DNSAAAARecord to hostname to indicate it has IPV6

    hns = Hostname.objects.raw(get_rules()["ipv6_webservers"]["query"])
    assert len(hns) == 0


def test_ns_ipv6_query(xtdb):
    network = Network.objects.create(name="test")
    hn = Hostname.objects.create(network=network, name="test.com")
    ns = Hostname.objects.create(network=network, name="ns1.test.com")
    DNSNSRecord.objects.create(hostname=hn, name_server=ns)

    hns = Hostname.objects.raw(get_rules()["ipv6_nameservers"]["query"])
    assert len(hns) == 1
    assert hns[0].name == "ns1.test.com"

    ip = IPAddress.objects.create(network=network, address="2001:ab8:d0cb::")
    DNSAAAARecord.objects.create(hostname=ns, ip_address=ip)  # Add DNSAAAARecord to nameserver to indicate it has IPV6

    hns = Hostname.objects.raw(get_rules()["ipv6_nameservers"]["query"])
    assert len(hns) == 0


def test_missing_spf(xtdb):
    network = Network.objects.create(name="test")
    hn = Hostname.objects.create(network=network, name="test.com")

    assert len(Hostname.objects.raw(get_rules()["missing_spf"]["query"])) == 1
    assert Hostname.objects.raw(get_rules()["missing_spf"]["query"])[0].name == "test.com"

    DNSTXTRecord.objects.create(hostname=hn, value="vspf1")
    assert len(Hostname.objects.raw(get_rules()["missing_spf"]["query"])) == 1

    DNSTXTRecord.objects.create(hostname=hn, value="v=spf1")
    assert len(Hostname.objects.raw(get_rules()["missing_spf"]["query"])) == 0

    DNSTXTRecord.objects.create(hostname=hn, value="random")
    assert len(Hostname.objects.raw(get_rules()["missing_spf"]["query"])) == 0

    DNSTXTRecord.objects.create(hostname=hn, value="v=spf1 number 2")
    assert len(Hostname.objects.raw(get_rules()["missing_spf"]["query"])) == 0


def test_port_classification(xtdb):
    network = Network.objects.create(name="test")
    assert len(IPAddress.objects.raw(get_rules()["open_sysadmin_port"]["query"])) == 0

    ip = IPAddress.objects.create(network=network, address="127.0.0.2")
    IPPort.objects.create(address=ip, protocol=Protocol.TCP, port=80, tls=False, service="unknown")
    assert len(IPAddress.objects.raw(get_rules()["open_sysadmin_port"]["query"])) == 0

    ip = IPAddress.objects.create(network=network, address="127.0.0.3")
    IPPort.objects.create(address=ip, protocol=Protocol.TCP, port=21, tls=False, service="unknown")
    assert len(IPAddress.objects.raw(get_rules()["open_sysadmin_port"]["query"])) == 1

    ip = IPAddress.objects.create(network=network, address="127.0.0.4")
    IPPort.objects.create(address=ip, protocol=Protocol.TCP, port=22, tls=False, service="unknown")
    assert len(IPAddress.objects.raw(get_rules()["open_sysadmin_port"]["query"])) == 2

    assert len(IPAddress.objects.raw(get_rules()["open_database_port"]["query"])) == 0

    ip = IPAddress.objects.create(network=network, address="127.0.0.5")
    IPPort.objects.create(address=ip, protocol=Protocol.TCP, port=5432, tls=False, service="unknown")
    assert len(IPAddress.objects.raw(get_rules()["open_database_port"]["query"])) == 1

    assert len(IPAddress.objects.raw(get_rules()["open_remote_desktop_port"]["query"])) == 0

    ip = IPAddress.objects.create(network=network, address="127.0.0.6")
    IPPort.objects.create(address=ip, protocol=Protocol.TCP, port=3389, tls=False, service="unknown")
    assert len(IPAddress.objects.raw(get_rules()["open_remote_desktop_port"]["query"])) == 1

    assert len(IPAddress.objects.raw(get_rules()["open_uncommon_port"]["query"])) == 0

    ip = IPAddress.objects.create(network=network, address="127.0.0.7")
    IPPort.objects.create(address=ip, protocol=Protocol.UDP, port=53, tls=False, service="unknown")
    assert len(IPAddress.objects.raw(get_rules()["open_uncommon_port"]["query"])) == 0

    ip = IPAddress.objects.create(network=network, address="127.0.0.8")
    IPPort.objects.create(address=ip, protocol=Protocol.TCP, port=12345, tls=False, service="unknown")
    assert len(IPAddress.objects.raw(get_rules()["open_uncommon_port"]["query"])) == 1

    assert len(IPAddress.objects.raw(get_rules()["open_common_port"]["query"])) == 6


def test_missing_caa(xtdb):
    network = Network.objects.create(name="test")
    hn = Hostname.objects.create(network=network, name="test.com")
    hn2 = Hostname.objects.create(network=network, name="test2.com")

    assert len(IPAddress.objects.raw(get_rules()["missing_caa"]["query"])) == 2

    DNSCAARecord.objects.create(hostname=hn, flags=10, tag=CAATag.ISSUE, value="123")
    assert len(IPAddress.objects.raw(get_rules()["missing_caa"]["query"])) == 1

    DNSCAARecord.objects.create(hostname=hn2, flags=10, tag=CAATag.CONTACTEMAIL, value="321")
    assert len(IPAddress.objects.raw(get_rules()["missing_caa"]["query"])) == 0


def test_missing_dmarc(xtdb):
    network = Network.objects.create(name="test")
    h1 = Hostname.objects.create(network=network, name="test.com")
    h0 = Hostname.objects.create(network=network, name="some.test.com")
    h2 = Hostname.objects.create(network=network, name="test2.com")

    hostnames = Hostname.objects.raw(get_rules()["missing_dmarc"]["query"])
    assert {hostname.id for hostname in hostnames} == {h0.pk, h1.pk, h2.pk}

    DNSTXTRecord.objects.create(hostname=h1, value="v=DMARC1; p=none; sp=quarantine;", prefix="_dmarc")

    hostnames = Hostname.objects.raw(get_rules()["missing_dmarc"]["query"])
    assert {hostname.id for hostname in hostnames} == {h2.pk}


def test_domain_owner_verification(xtdb):
    network = Network.objects.create(name="test")
    hn = Hostname.objects.create(network=network, name="test.com")
    hn2 = Hostname.objects.create(network=network, name="test2.com")
    ns1 = Hostname.objects.create(network=network, name="ns1.test.com")
    ns2 = Hostname.objects.create(network=network, name="ns2.test.com")
    DNSNSRecord.objects.create(hostname=hn, name_server=ns1)
    DNSNSRecord.objects.create(hostname=hn, name_server=ns2)

    assert len(Hostname.objects.raw(get_rules()["domain_owner_verification"]["query"])) == 0

    pending = Hostname.objects.create(network=network, name="ns1.registrant-verification.ispapi.net")
    DNSNSRecord.objects.create(hostname=hn, name_server=pending)

    assert len(Hostname.objects.raw(get_rules()["domain_owner_verification"]["query"])) == 1
    assert Hostname.objects.raw(get_rules()["domain_owner_verification"]["query"])[0].name == "test.com"

    DNSNSRecord.objects.create(hostname=hn2, name_server=pending)
    assert len(Hostname.objects.raw(get_rules()["domain_owner_verification"]["query"])) == 2
    assert hn in list(Hostname.objects.raw(get_rules()["domain_owner_verification"]["query"]))
    assert hn2 in list(Hostname.objects.raw(get_rules()["domain_owner_verification"]["query"]))


def test_ipv6_webservers_inverse_query(xtdb):
    network = Network.objects.create(name="test")
    hn = Hostname.objects.create(network=network, name="test.com")

    finding_type, _ = FindingType.objects.get_or_create(code="KAT-WEBSERVER-NO-IPV6")
    finding = Finding.objects.create(finding_type=finding_type, hostname=hn)

    assert Finding.objects.filter(pk=finding.pk).exists()

    ip = IPAddress.objects.create(network=network, address="2001:ab8:d0cb::")
    DNSAAAARecord.objects.create(hostname=hn, ip_address=ip)

    with connections["xtdb"].cursor() as cursor:
        cursor.execute(get_rules()["ipv6_webservers"]["inverse_query"])

    assert not Finding.objects.filter(pk=finding.pk).exists()


def test_ipv6_nameservers_inverse_query(xtdb):
    network = Network.objects.create(name="test")
    hn = Hostname.objects.create(network=network, name="test.com")
    ns = Hostname.objects.create(network=network, name="ns1.test.com")
    DNSNSRecord.objects.create(hostname=hn, name_server=ns)

    # Create finding type and finding
    finding_type, _ = FindingType.objects.get_or_create(code="KAT-NAMESERVER-NO-IPV6")
    finding = Finding.objects.create(finding_type=finding_type, hostname=ns)

    # Verify finding exists
    assert Finding.objects.filter(pk=finding.pk).exists()

    # Add IPv6 support to nameserver
    ip = IPAddress.objects.create(network=network, address="2001:ab8:d0cb::")
    DNSAAAARecord.objects.create(hostname=ns, ip_address=ip)

    # Run inverse query
    with connections["xtdb"].cursor() as cursor:
        cursor.execute(get_rules()["ipv6_nameservers"]["inverse_query"])

    # Verify finding was deleted
    assert not Finding.objects.filter(pk=finding.pk).exists()


def test_missing_spf_inverse_query(xtdb):
    """Test that inverse query removes findings when SPF record is added"""
    network = Network.objects.create(name="test")
    hn = Hostname.objects.create(network=network, name="test.com")

    # Create finding type and finding
    finding_type, _ = FindingType.objects.get_or_create(code="KAT-NO-SPF")
    finding = Finding.objects.create(finding_type=finding_type, hostname=hn)

    # Verify finding exists
    assert Finding.objects.filter(pk=finding.pk).exists()

    # Add SPF record
    DNSTXTRecord.objects.create(hostname=hn, value="v=spf1 -all")

    # Run inverse query
    with connections["xtdb"].cursor() as cursor:
        cursor.execute(get_rules()["missing_spf"]["inverse_query"])

    # Verify finding was deleted
    assert not Finding.objects.filter(pk=finding.pk).exists()


def test_open_sysadmin_port_inverse_query(xtdb):
    """Test that inverse query removes findings when sysadmin port is closed"""
    network = Network.objects.create(name="test")
    ip = IPAddress.objects.create(network=network, address="127.0.0.1")
    port = IPPort.objects.create(address=ip, protocol=Protocol.TCP, port=22, tls=False, service="ssh")

    # Create finding type and finding
    finding_type, _ = FindingType.objects.get_or_create(code="KAT-OPEN-SYSADMIN-PORT")
    finding = Finding.objects.create(finding_type=finding_type, address=ip)

    # Verify finding exists
    assert Finding.objects.filter(pk=finding.pk).exists()

    # Close the port
    port.delete()

    # Run inverse query
    with connections["xtdb"].cursor() as cursor:
        cursor.execute(get_rules()["open_sysadmin_port"]["inverse_query"])

    # Verify finding was deleted
    assert not Finding.objects.filter(pk=finding.pk).exists()


def test_open_database_port_inverse_query(xtdb):
    """Test that inverse query removes findings when database port is closed"""
    network = Network.objects.create(name="test")
    ip = IPAddress.objects.create(network=network, address="127.0.0.1")
    port = IPPort.objects.create(address=ip, protocol=Protocol.TCP, port=5432, tls=False, service="postgres")

    # Create finding type and finding
    finding_type, _ = FindingType.objects.get_or_create(code="KAT-OPEN-DATABASE-PORT")
    finding = Finding.objects.create(finding_type=finding_type, address=ip)

    # Verify finding exists
    assert Finding.objects.filter(pk=finding.pk).exists()

    # Close the port
    port.delete()

    # Run inverse query
    with connections["xtdb"].cursor() as cursor:
        cursor.execute(get_rules()["open_database_port"]["inverse_query"])

    # Verify finding was deleted
    assert not Finding.objects.filter(pk=finding.pk).exists()


def test_open_remote_desktop_port_inverse_query(xtdb):
    """Test that inverse query removes findings when RDP port is closed"""
    network = Network.objects.create(name="test")
    ip = IPAddress.objects.create(network=network, address="127.0.0.1")
    port = IPPort.objects.create(address=ip, protocol=Protocol.TCP, port=3389, tls=False, service="rdp")

    # Create finding type and finding
    finding_type, _ = FindingType.objects.get_or_create(code="KAT-REMOTE-DESKTOP-PORT")
    finding = Finding.objects.create(finding_type=finding_type, address=ip)

    # Verify finding exists
    assert Finding.objects.filter(pk=finding.pk).exists()

    # Close the port
    port.delete()

    # Run inverse query
    with connections["xtdb"].cursor() as cursor:
        cursor.execute(get_rules()["open_remote_desktop_port"]["inverse_query"])

    # Verify finding was deleted
    assert not Finding.objects.filter(pk=finding.pk).exists()


def test_open_uncommon_port_inverse_query(xtdb):
    """Test that inverse query removes findings when uncommon port is closed"""
    network = Network.objects.create(name="test")
    ip = IPAddress.objects.create(network=network, address="127.0.0.1")
    port = IPPort.objects.create(address=ip, protocol=Protocol.TCP, port=12345, tls=False, service="custom")

    # Create finding type and finding
    finding_type, _ = FindingType.objects.get_or_create(code="KAT-UNCOMMON-OPEN-PORT")
    finding = Finding.objects.create(finding_type=finding_type, address=ip)

    # Verify finding exists
    assert Finding.objects.filter(pk=finding.pk).exists()

    # Close the port
    port.delete()

    # Run inverse query
    with connections["xtdb"].cursor() as cursor:
        cursor.execute(get_rules()["open_uncommon_port"]["inverse_query"])

    # Verify finding was deleted
    assert not Finding.objects.filter(pk=finding.pk).exists()


def test_open_common_port_inverse_query(xtdb):
    """Test that inverse query removes findings when common port is closed"""
    network = Network.objects.create(name="test")
    ip = IPAddress.objects.create(network=network, address="127.0.0.1")
    port = IPPort.objects.create(address=ip, protocol=Protocol.TCP, port=80, tls=False, service="http")

    # Create finding type and finding
    finding_type, _ = FindingType.objects.get_or_create(code="KAT-OPEN-COMMON-PORT")
    finding = Finding.objects.create(finding_type=finding_type, address=ip)

    # Verify finding exists
    assert Finding.objects.filter(pk=finding.pk).exists()

    # Close the port
    port.delete()

    # Run inverse query
    with connections["xtdb"].cursor() as cursor:
        cursor.execute(get_rules()["open_common_port"]["inverse_query"])

    # Verify finding was deleted
    assert not Finding.objects.filter(pk=finding.pk).exists()


def test_missing_caa_inverse_query(xtdb):
    """Test that inverse query removes findings when CAA record is added"""
    network = Network.objects.create(name="test")
    hn = Hostname.objects.create(network=network, name="test.com")

    # Create finding type and finding
    finding_type, _ = FindingType.objects.get_or_create(code="KAT-NO-CAA")
    finding = Finding.objects.create(finding_type=finding_type, hostname=hn)

    # Verify finding exists
    assert Finding.objects.filter(pk=finding.pk).exists()

    # Add CAA record
    DNSCAARecord.objects.create(hostname=hn, flags=0, tag=CAATag.ISSUE, value="letsencrypt.org")

    # Run inverse query
    with connections["xtdb"].cursor() as cursor:
        cursor.execute(get_rules()["missing_caa"]["inverse_query"])

    # Verify finding was deleted
    assert not Finding.objects.filter(pk=finding.pk).exists()


def test_missing_dmarc_inverse_query(xtdb):
    """Test that inverse query removes findings when DMARC record is added"""
    network = Network.objects.create(name="test")
    h = Hostname.objects.create(network=network, name="test.com")
    hn = Hostname.objects.create(network=network, name="mx.test.com")
    DNSMXRecord.objects.create(hostname=h, preference=10, mail_server=hn)

    # Create finding type and finding
    finding_type, _ = FindingType.objects.get_or_create(code="KAT-NO-DMARC")
    finding = Finding.objects.create(finding_type=finding_type, hostname=hn)

    # Verify finding exists
    assert Finding.objects.filter(pk=finding.pk).exists()

    # Add DMARC record
    DNSTXTRecord.objects.create(hostname=hn, value="v=DMARC1; p=none;", prefix="_dmarc")

    # Run inverse query
    with connections["xtdb"].cursor() as cursor:
        cursor.execute(get_rules()["missing_dmarc"]["inverse_query"])

    assert not Finding.objects.filter(pk=finding.pk).exists()


def test_domain_owner_verification_inverse_query(xtdb):
    """Test that inverse query removes findings when pending nameserver is removed"""
    network = Network.objects.create(name="test")
    hn = Hostname.objects.create(network=network, name="test.com")
    pending = Hostname.objects.create(network=network, name="ns1.registrant-verification.ispapi.net")
    ns_record = DNSNSRecord.objects.create(hostname=hn, name_server=pending)

    finding_type, _ = FindingType.objects.get_or_create(code="KAT-DOMAIN-OWNERSHIP-PENDING")
    finding = Finding.objects.create(finding_type=finding_type, hostname=hn)

    assert Finding.objects.filter(pk=finding.pk).exists()
    ns_record.delete()

    with connections["xtdb"].cursor() as cursor:
        cursor.execute(get_rules()["domain_owner_verification"]["inverse_query"])

    assert not Finding.objects.filter(pk=finding.pk).exists()
