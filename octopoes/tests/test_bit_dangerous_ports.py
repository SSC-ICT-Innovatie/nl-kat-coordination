from bits.dangerous_ports.dangerous_ports import run

from octopoes.models.ooi.network import IPPort

ADDR = "address|8.8.8.8"


def _port(port, protocol="tcp"):
    return IPPort(address=ADDR, protocol=protocol, port=port)


def _findings(port):
    return [r for r in run(port, [], {}) if r.object_type == "Finding"]


def test_redis_dangerous():
    findings = _findings(_port(6379))
    assert len(findings) == 1
    assert "Redis" in findings[0].description


def test_mongodb_dangerous():
    findings = _findings(_port(27017))
    assert len(findings) == 1
    assert "MongoDB" in findings[0].description


def test_docker_api_dangerous():
    findings = _findings(_port(2375))
    assert len(findings) == 1
    assert "Docker" in findings[0].description


def test_kubernetes_dangerous():
    findings = _findings(_port(10250))
    assert len(findings) == 1
    assert "Kubernetes" in findings[0].description


def test_elasticsearch_dangerous():
    findings = _findings(_port(9200))
    assert len(findings) == 1
    assert "Elasticsearch" in findings[0].description


def test_telnet_insecure_protocol():
    findings = _findings(_port(23))
    assert len(findings) == 1
    assert "Telnet" in findings[0].description


def test_ftp_insecure_protocol():
    findings = _findings(_port(21))
    assert len(findings) == 1
    assert "FTP" in findings[0].description


def test_safe_port_clean():
    assert _findings(_port(80)) == []


def test_safe_port_443_clean():
    assert _findings(_port(443)) == []


def test_udp_not_checked():
    assert _findings(_port(6379, protocol="udp")) == []
