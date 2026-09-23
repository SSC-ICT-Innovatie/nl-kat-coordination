from boefjes.plugins.kat_service_banner.normalize import parse_software, run
from octopoes.models.ooi.network import IPAddressV4, IPPort, Network, PortState, Protocol
from octopoes.models.ooi.software import Software, SoftwareInstance

_ip = IPAddressV4(network=Network(name="internet").reference, address="1.2.3.4")
_port = IPPort(address=_ip.reference, protocol=Protocol.TCP, port=22, state=PortState.OPEN)
input_ooi = {"primary_key": str(_port.reference)}


def test_parse_software_ssh():
    assert parse_software("SSH-2.0-OpenSSH_8.4p1 Debian-5+deb11u2") == ("OpenSSH", "8.4p1")
    assert parse_software("SSH-2.0-dropbear_2020.81") == ("dropbear", "2020.81")


def test_parse_software_vsftpd():
    assert parse_software("220 (vsFTPd 3.0.3)") == ("vsFTPd", "3.0.3")


def test_parse_software_unrecognised_returns_none():
    # No fabrication from an ambiguous banner.
    assert parse_software("220 mail.example.com ESMTP") is None
    assert parse_software("HTTP/1.1 200 OK") is None
    assert parse_software("") is None


def test_run_yields_software_bound_to_ipport():
    oois = list(run(input_ooi, b"SSH-2.0-OpenSSH_8.4p1 Debian-5+deb11u2"))

    software = [o for o in oois if isinstance(o, Software)]
    instances = [o for o in oois if isinstance(o, SoftwareInstance)]
    assert len(software) == 1
    assert software[0].name == "OpenSSH"
    assert software[0].version == "8.4p1"
    assert len(instances) == 1
    assert instances[0].ooi == _port.reference


def test_run_yields_nothing_for_unrecognised_banner():
    assert list(run(input_ooi, b"nonsense banner")) == []
