from bits.software_cve.software_cve import run

from octopoes.models import Reference
from octopoes.models.ooi.software import Software, SoftwareInstance

OOI_REF = Reference.from_str("IPAddressV4|internet|1.1.1.1")


def _software(name, version=None):
    return Software(name=name, version=version)


def _instance(software):
    return SoftwareInstance(ooi=OOI_REF, software=software.reference)


def _findings(software, instances):
    return [r for r in run(software, instances, {}) if r.object_type == "Finding"]


def test_log4j_vulnerable():
    sw = _software("log4j", "2.14.0")
    results = _findings(sw, [_instance(sw)])
    assert len(results) == 1
    assert "CVE-2021-44228" in results[0].description


def test_log4j_safe_version():
    sw = _software("log4j", "2.15.0")
    assert _findings(sw, [_instance(sw)]) == []


def test_openssl_vulnerable():
    sw = _software("openssl", "1.0.1f")
    results = _findings(sw, [_instance(sw)])
    assert any("CVE-2016-0800" in r.description for r in results)


def test_no_version_skipped():
    sw = _software("openssl")
    assert _findings(sw, [_instance(sw)]) == []


def test_unknown_software_clean():
    sw = _software("some-unknown-app", "1.0.0")
    assert _findings(sw, [_instance(sw)]) == []


def test_openssh_regresshion():
    sw = _software("openssh", "9.7")
    results = _findings(sw, [_instance(sw)])
    assert any("CVE-2024-6387" in r.description for r in results)


def test_openssh_safe():
    sw = _software("openssh", "9.8")
    assert _findings(sw, [_instance(sw)]) == []


def test_name_normalization():
    """OpenSSH, open-ssh, and OPENSSH should all match the database entry."""
    sw = _software("OpenSSH", "9.7")
    results = _findings(sw, [_instance(sw)])
    assert any("CVE-2024-6387" in r.description for r in results)
