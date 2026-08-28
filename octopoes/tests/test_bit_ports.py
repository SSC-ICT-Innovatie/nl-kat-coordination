from nibbles.port_classification_ip.port_classification_ip import nibble as run_port_classification

from octopoes.models.ooi.config import Config
from octopoes.models.ooi.findings import Finding
from octopoes.models.ooi.network import IPAddressV4, IPPort


def test_port_classification_tcp_80():
    address = IPAddressV4(address="8.8.8.8", network="network|fake")
    port = IPPort(address=address.reference, protocol="tcp", port=80)
    results = list(run_port_classification(port, None))

    assert not results


def test_port_classification_udp_53():
    address = IPAddressV4(address="8.8.8.8", network="network|fake")
    port = IPPort(address=address.reference, protocol="tcp", port=53)
    results = list(run_port_classification(port, None))

    assert not results


def test_port_classification_tcp_22():
    address = IPAddressV4(address="8.8.8.8", network="network|fake")
    port = IPPort(address=address.reference, protocol="tcp", port=22)
    results = list(run_port_classification(port, None))

    assert len(results) == 2
    finding = results[-1]
    assert isinstance(finding, Finding)
    assert finding.description == "Port 22/tcp is a system administrator port and should possibly not be open."


def test_port_classification_tcp_5432():
    address = IPAddressV4(address="8.8.8.8", network="network|fake")
    port = IPPort(address=address.reference, protocol="tcp", port=5432)
    results = list(run_port_classification(port, None))

    assert len(results) == 2
    finding = results[-1]
    assert isinstance(finding, Finding)
    assert finding.description == "Port 5432/tcp is a database port and should not be open."


def test_port_classification_tcp_12345():
    address = IPAddressV4(address="8.8.8.8", network="network|fake")
    port = IPPort(address=address.reference, protocol="tcp", port=12345)
    results = list(run_port_classification(port, None))

    assert len(results) == 2
    finding = results[-1]
    assert isinstance(finding, Finding)
    assert finding.description == "Port 12345/tcp is not a common port and should possibly not be open."


def test_port_classification_tcp_3306_with_config():
    address = IPAddressV4(address="8.8.8.8", network="network|fake")
    port = IPPort(address=address.reference, protocol="tcp", port=3306)
    results = list(
        run_port_classification(
            port, Config(ooi=address.reference, bit_id="port-classification-ip", config={"db_tcp_ports": "1234"})
        )
    )

    assert len(results) == 2
    finding = results[-1]
    assert isinstance(finding, Finding)
    assert finding.description == "Port 3306/tcp is not a common port and should possibly not be open."


def test_port_classification_udp_80():
    address = IPAddressV4(address="8.8.8.8", network="network|fake")
    port = IPPort(address=address.reference, protocol="udp", port=80)
    results = list(run_port_classification(port, None))

    assert len(results) == 2
    finding = results[-1]
    assert isinstance(finding, Finding)
    assert finding.description == "Port 80/udp is not a common port and should possibly not be open."
