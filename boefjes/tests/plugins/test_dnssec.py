import subprocess

import pytest

from boefjes.plugins.kat_dnssec import main as dnssec_main
from boefjes.plugins.kat_dnssec.normalize import run
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network
from tests.loading import get_dummy_data


def fake_drill(returncode: int, stdout: bytes = b"", stderr: bytes = b""):
    def fake_run(cmd, capture_output):
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

    with pytest.raises(RuntimeError, match="outbound UDP and TCP port 53"):
        dnssec_main.run({"arguments": {"input": {"name": "example.org"}}})


def test_boefje_drill_failure_includes_stderr(monkeypatch):
    monkeypatch.setattr(dnssec_main.subprocess, "run", fake_drill(1, stderr=b"Error: error sending query\n"))

    with pytest.raises(RuntimeError, match=r"status 1 for example\.org \(A\): Error: error sending query"):
        dnssec_main.run({"arguments": {"input": {"name": "example.org"}}})


def test_dnssec_unsigned():
    input_ooi = Hostname(network=Network(name="internet").reference, name="example.org")
    output = list(run(input_ooi.serialize(), get_dummy_data("inputs/dnssec-unsigned.txt")))

    assert output[1].primary_key == "Finding|Hostname|internet|example.org|KAT-NO-DNSSEC"


def test_dnssec_invalid():
    input_ooi = Hostname(network=Network(name="internet").reference, name="example.org")
    output = list(run(input_ooi.serialize(), get_dummy_data("inputs/dnssec-self-signed.txt")))

    assert output[1].primary_key == "Finding|Hostname|internet|example.org|KAT-INVALID-DNSSEC"


def test_dnssec_valid():
    input_ooi = Hostname(network=Network(name="internet").reference, name="example.org")
    output = list(run(input_ooi.serialize(), get_dummy_data("inputs/dnssec-valid.txt")))

    assert len(output) == 0


def test_dnssec_status_line_not_last_line():
    input_ooi = Hostname(network=Network(name="internet").reference, name="ps4.platformrijksoverheid.nl")
    output = list(run(input_ooi.serialize(), get_dummy_data("inputs/dnssec-status-line-not-last-line.txt")))

    assert len(output) == 0
