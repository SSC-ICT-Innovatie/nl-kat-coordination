import subprocess

import pytest

from boefjes.plugins.kat_dnssec import main as dnssec_main
from boefjes.plugins.kat_dnssec.normalize import run
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network
from tests.loading import get_dummy_data


def fake_drill(returncode: int, stdout: bytes = b"", stderr: bytes = b""):
    def fake_run(cmd, capture_output, timeout):
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

    return fake_run


def test_boefje_drill_success_returns_raw_output(monkeypatch):
    monkeypatch.setattr(dnssec_main.subprocess, "run", fake_drill(0, stdout=b"[T] example.org. 3600 IN A 192.0.2.1\n"))

    output = dnssec_main.run({"arguments": {"input": {"name": "example.org"}}})

    assert output == [({"openkat/dnssec-output"}, b"[T] example.org. 3600 IN A 192.0.2.1\n")]


def test_boefje_drill_network_error_gives_clear_message(monkeypatch):
    monkeypatch.setattr(
        dnssec_main.subprocess,
        "run",
        fake_drill(20, stderr=b"Error sending query: Could not send or receive, because of network error\n"),
    )

    with pytest.raises(RuntimeError, match="connectivity problem rather than the domain's DNSSEC state"):
        dnssec_main.run({"arguments": {"input": {"name": "example.org"}}})


def test_boefje_drill_failure_includes_stderr(monkeypatch):
    monkeypatch.setattr(dnssec_main.subprocess, "run", fake_drill(1, stderr=b"Error: error sending query\n"))

    with pytest.raises(RuntimeError, match=r"status 1 for example\.org \(A\): Error: error sending query"):
        dnssec_main.run({"arguments": {"input": {"name": "example.org"}}})


def test_dnssec_unsigned():
    input_ooi = Hostname(network=Network(name="internet").reference, name="google.com")
    output = list(run(input_ooi.serialize(), get_dummy_data("inputs/dnssec-unsigned.txt")))

    assert output[1].primary_key == "Finding|Hostname|internet|google.com|KAT-NO-DNSSEC"


def test_dnssec_invalid():
    input_ooi = Hostname(network=Network(name="internet").reference, name="dnssec-failed.org")
    output = list(run(input_ooi.serialize(), get_dummy_data("inputs/dnssec-self-signed.txt")))

    assert output[1].primary_key == "Finding|Hostname|internet|dnssec-failed.org|KAT-INVALID-DNSSEC"


def test_dnssec_valid():
    input_ooi = Hostname(network=Network(name="internet").reference, name="ok.ok.ok.bad-dnssec.wb.sidnlabs.nl")
    output = list(run(input_ooi.serialize(), get_dummy_data("inputs/dnssec-valid.txt")))

    assert len(output) == 0


def test_dnssec_status_line_not_last_line():
    input_ooi = Hostname(network=Network(name="internet").reference, name="ps4.platformrijksoverheid.nl")
    output = list(run(input_ooi.serialize(), get_dummy_data("inputs/dnssec-status-line-not-last-line.txt")))

    assert len(output) == 0


def test_dnssec_signed_domain_with_unsigned_cname_target():
    """A signed domain whose CNAME points at an unsigned host must not be
    reported as KAT-NO-DNSSEC: the last [U] status line belongs to the CNAME
    target, not to the queried domain (#4277)."""
    input_ooi = Hostname(network=Network(name="internet").reference, name="signed.example.nl")

    output = list(run(input_ooi.serialize(), get_dummy_data("inputs/dnssec-cname-to-unsigned.txt")))

    assert len(output) == 0


def test_dnssec_missing_domain_section_rejected():
    input_ooi = Hostname(network=Network(name="internet").reference, name="example.org")
    with pytest.raises(ValueError, match="No DNSSEC answer status"):
        list(run(input_ooi.serialize(), b";; Domain: other.org.\n[U] other.org. 300 IN A 192.0.2.1\n"))


def test_dnssec_ignores_dnskey_and_other_owner():
    input_ooi = Hostname(network=Network(name="internet").reference, name="example.org")
    raw = (
        b";; Domain: example.org.\n[B] example.org. 300 IN DNSKEY 257 3 8 xyz\n"
        b"[U] other.org. 300 IN A 192.0.2.1\n[T] example.org. 300 IN A 192.0.2.2\n"
    )
    assert list(run(input_ooi.serialize(), raw)) == []


def test_dnssec_case_insensitive_domain_and_trailing_dot():
    input_ooi = Hostname(network=Network(name="internet").reference, name="example.org")
    raw = b";; Domain: EXAMPLE.ORG.\n[U] Example.Org. 300 IN AAAA 2001:db8::1\n"
    assert list(run(input_ooi.serialize(), raw))[1].primary_key == "Finding|Hostname|internet|example.org|KAT-NO-DNSSEC"


def test_dnssec_timeout(monkeypatch):
    def timeout(cmd, capture_output, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(dnssec_main.subprocess, "run", timeout)
    with pytest.raises(RuntimeError, match="timed out"):
        dnssec_main.run({"arguments": {"input": {"name": "example.org"}}})


@pytest.mark.parametrize("domain", ["bad_name.org", "-bad.org", "bad-.org", "example..org", "https://example.org"])
def test_dnssec_invalid_hostname(domain):
    with pytest.raises(ValueError):
        dnssec_main.normalize_hostname(domain)


def test_dnssec_idna_hostname():
    assert dnssec_main.normalize_hostname("Bücher.de.") == "xn--bcher-kva.de"


def test_dnssec_signed_nodata_falls_back_to_aaaa(monkeypatch):
    calls = []

    def fake_run(domain, record_type):
        calls.append(record_type)
        if record_type != "AAAA":
            return f"[T] No data found for: {domain}. type {record_type}".encode()
        return b";; Domain: example.org.\n[T] example.org. 300 IN AAAA 2001:db8::1\n"

    monkeypatch.setattr(dnssec_main, "run_drill", fake_run)
    dnssec_main.run({"arguments": {"input": {"name": "example.org"}}})
    assert calls == ["A", "CNAME", "AAAA"]


def test_dnssec_signed_nodata_without_address_records_is_trusted():
    raw = (
        b";; Domain: nl.\n"
        b"[T] nl. 3600 IN DNSKEY 256 3 13 ;{id = 60847 (zsk), size = 256b}\n"
        b"[T] Existence denied: nl. A\n"
    )
    input_ooi = Hostname(network=Network(name="internet").reference, name="nl")
    assert list(run(input_ooi.serialize(), raw)) == []


def test_dnssec_answer_outside_matching_drill_section():
    input_ooi = Hostname(network=Network(name="internet").reference, name="example.org")
    raw = b";; Domain: org.\n[T] org. 300 IN DNSKEY 257 3 8 xyz\n[U] example.org. 300 IN A 192.0.2.1\n"
    output = list(run(input_ooi.serialize(), raw))
    assert output[1].primary_key == "Finding|Hostname|internet|example.org|KAT-NO-DNSSEC"


def test_dnssec_bogus_uses_invalid_finding_type():
    input_ooi = Hostname(network=Network(name="internet").reference, name="example.org")
    raw = b"[B] example.org. 300 IN A 192.0.2.1\n"
    output = list(run(input_ooi.serialize(), raw))
    assert output[1].primary_key == "Finding|Hostname|internet|example.org|KAT-INVALID-DNSSEC"


def test_dnssec_self_signed_uses_invalid_finding_type():
    input_ooi = Hostname(network=Network(name="internet").reference, name="example.org")
    raw = b"[S] example.org. 300 IN A 192.0.2.1\n"
    output = list(run(input_ooi.serialize(), raw))
    assert output[1].primary_key == "Finding|Hostname|internet|example.org|KAT-INVALID-DNSSEC"


def test_dnssec_finding_types_present_in_catalog():
    import json
    from pathlib import Path

    catalog = Path(__file__).resolve().parents[2] / "boefjes/plugins/kat_kat_finding_types/kat_finding_types.json"
    types = json.loads(catalog.read_text())
    for finding_id in ("KAT-NO-DNSSEC", "KAT-INVALID-DNSSEC", "KAT-INVALID-DNSSEC"):
        assert finding_id in types
        assert all(types[finding_id].get(key) for key in ("name", "description", "risk", "impact", "recommendation"))
