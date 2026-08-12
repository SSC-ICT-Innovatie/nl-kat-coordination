import re

import pytest
from jsonschema.exceptions import ValidationError
from jsonschema.validators import validate

from boefjes.plugins.kat_nmap_tcp.normalize import run
from octopoes.models.ooi.network import IPAddressV4, Network
from octopoes.models.ooi.software import Software, SoftwareInstance
from tests.loading import get_dummy_data


def test_normalizer():
    input_ooi = IPAddressV4(network=Network(name="internet").reference, address="134.209.85.72")
    output = list(run(input_ooi.serialize(), get_dummy_data("raw/nmap_mispoes.xml")))
    assert len(output) == 25
    for i, out in enumerate(output[:-1]):
        if out.object_type == "IPPort" and output[i + 1].object_type == "Service":
            name = output[i + 1].name
            if out.port == 80:
                assert name == "http"
            elif out.port == 443:
                assert name == "https"
            else:
                assert name != "http"
                assert name != "https"


def test_normalizer_extracts_software_from_cpes():
    input_ooi = IPAddressV4(network=Network(name="internet").reference, address="134.209.85.72")
    output = list(run(input_ooi.serialize(), get_dummy_data("raw/nmap_mispoes.xml")))

    software = {(s.name, s.version, s.cpe) for s in output if isinstance(s, Software)}
    assert ("openssh", "8.4p1", "cpe:/a:openbsd:openssh:8.4p1") in software
    assert ("bind", "9.16.44", "cpe:/a:isc:bind:9.16.44") in software
    assert ("nginx", "1.18.0", "cpe:/a:igor_sysoev:nginx:1.18.0") in software
    assert ("mysql", None, "cpe:/a:mysql:mysql") in software
    # Operating-system CPEs (cpe:/o:...) describe the host, not the service.
    assert not any(s.cpe and s.cpe.startswith("cpe:/o:") for s in output if isinstance(s, Software))

    # Every Software is bound to the IPService it was detected on.
    instances = [si for si in output if isinstance(si, SoftwareInstance)]
    assert len(instances) == 5
    assert all(si.ooi.class_ == "IPService" for si in instances)


def get_pattern():
    max_65535 = r"(6553[0-5]|655[0-2]\d|65[0-4]\d{2}|6[0-4]\d{3}|[1-5]\d{4}|\d{1,4})"
    max_65535_or_port_range = f"({max_65535}|{max_65535}-{max_65535})"
    one_or_comma_separated = f"^{max_65535_or_port_range}$|^{max_65535_or_port_range}(,{max_65535_or_port_range})+$"

    return re.compile(one_or_comma_separated)


def test_single_port_pattern(local_repository):
    schema = local_repository.schema("nmap-ports")
    for single_port in ["1", "2", "20", "80", "200", "2000", "20000", "65535"]:
        assert get_pattern().search(single_port) is not None
        validate(instance={"PORTS": single_port}, schema=schema)


def test_bad_single_port_pattern(local_repository):
    schema = local_repository.schema("nmap-ports")
    for bad_single_port in ["-1", "-2000", "65536", "222222"]:
        assert get_pattern().search(bad_single_port) is None
        with pytest.raises(ValidationError):
            validate(instance={"PORTS": bad_single_port}, schema=schema)


def test_multi_ports_pattern(local_repository):
    schema = local_repository.schema("nmap-ports")
    for multi_port in ["1,2", "2,3,4", "2,3,4,5,6,7", "2,20,200,2000,65535"]:
        assert get_pattern().search(multi_port) is not None
        validate(instance={"PORTS": multi_port}, schema=schema)


def test_port_range_pattern(local_repository):
    schema = local_repository.schema("nmap-ports")
    for port_range in ["1-2", "2-20000", "65533-65535"]:
        assert get_pattern().search(port_range) is not None
        validate(instance={"PORTS": port_range}, schema=schema)


def test_combined(local_repository):
    schema = local_repository.schema("nmap-ports")
    for port_range in ["1,1-65000", "1,2,234,4300-5999,1", "22,111,137,80-100"]:
        assert get_pattern().search(port_range) is not None
        validate(instance={"PORTS": port_range}, schema=schema)


def test_badly_combined(local_repository):
    schema = local_repository.schema("nmap-ports")
    for port_range in ["1,1-", "1-234-323"]:
        assert get_pattern().search(port_range) is None
        with pytest.raises(ValidationError):
            validate(instance={"PORTS": port_range}, schema=schema)
