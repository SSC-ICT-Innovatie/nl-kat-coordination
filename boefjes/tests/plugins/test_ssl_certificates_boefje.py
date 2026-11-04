import subprocess

import pytest

from boefjes.plugins.kat_ssl_certificates import main

PEM_OUTPUT = b"""CONNECTED(00000003)
---
Certificate chain
 0 s:CN = rc4.badssl.com
   i:C = US, O = Let's Encrypt, CN = R3
-----BEGIN CERTIFICATE-----
MIIFKjCCBBKgAwIBAgISBIEgUTAliVGEWSjvwigTdO8TMA0GCSqGSIb3DQEBCwUA
-----END CERTIFICATE-----
---
"""


def _meta(ip: str, port: int = 443, scheme: str = "https", input_type: str = "HostnameIPService") -> dict:
    input_: dict = {
        "object_type": input_type,
        "ip_service": {"service": {"name": scheme}, "ip_port": {"address": {"address": ip}, "port": port}},
        "oci_arguments": ["s_client", "-prexit", "-showcerts"],
    }
    if input_type == "IPService":
        pass  # a serialized IPService carries no hostname
    else:
        input_["hostname"] = {"name": "example.com"}
    return {"arguments": {"input": input_, "oci_arguments": ["s_client", "-prexit", "-showcerts"]}}


def _fake_run(returncode: int, stdout: bytes = b"", stderr: bytes = b""):
    def fake_run(cmd, capture_output):
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

    return fake_run


def test_ipv6_address_wrapped_in_brackets(monkeypatch):
    captured = {}

    def fake_run(cmd, capture_output):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=PEM_OUTPUT, stderr=b"")

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    main.run(_meta("2001:610:2d8:401::33:18"))

    idx = captured["cmd"].index("-host")
    assert captured["cmd"][idx + 1] == "[2001:610:2d8:401::33:18]"


def test_ipv4_address_not_wrapped(monkeypatch):
    captured = {}

    def fake_run(cmd, capture_output):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=PEM_OUTPUT, stderr=b"")

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    main.run(_meta("192.0.2.1"))

    idx = captured["cmd"].index("-host")
    assert captured["cmd"][idx + 1] == "192.0.2.1"


def test_sni_sent_for_hostname_input(monkeypatch):
    captured = {}

    def fake_run(cmd, capture_output):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=PEM_OUTPUT, stderr=b"")

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    main.run(_meta("192.0.2.1"))

    idx = captured["cmd"].index("-servername")
    assert captured["cmd"][idx + 1] == "example.com"


def test_no_sni_for_ip_service_input(monkeypatch):
    """A bare IPService input is a connection without a server name."""
    captured = {}

    def fake_run(cmd, capture_output):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=PEM_OUTPUT, stderr=b"")

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    main.run(_meta("192.0.2.1", input_type="IPService"))

    assert "-servername" not in captured["cmd"]


def test_sni_still_sent_for_legacy_website_input(monkeypatch):
    """Until the consumes list flips, the boefje is scheduled with Website
    inputs; those must keep their SNI unchanged."""
    captured = {}

    def fake_run(cmd, capture_output):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=PEM_OUTPUT, stderr=b"")

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    main.run(_meta("192.0.2.1", input_type="Website"))

    idx = captured["cmd"].index("-servername")
    assert captured["cmd"][idx + 1] == "example.com"


def test_failure_crashes_task_with_called_process_error(monkeypatch):
    """A handshake with no certificate data crashes the task (unchanged
    behavior). What to record about the failure is a separate decision."""
    stderr = b"connect:errno=101\nNetwork unreachable\n"
    monkeypatch.setattr(main.subprocess, "run", _fake_run(1, stderr=stderr))

    with pytest.raises(subprocess.CalledProcessError):
        main.run(_meta("192.0.2.1"))


def test_nonzero_exit_with_certificates_returns_output(monkeypatch):
    """A failed TLS handshake still yields the certificate chain (#5417)."""
    monkeypatch.setattr(main.subprocess, "run", _fake_run(1, stdout=PEM_OUTPUT, stderr=b"handshake failure"))

    output = main.run(_meta("192.0.2.1"))

    assert output == [({"openkat/ssl-certificates-output"}, PEM_OUTPUT.decode())]


def test_non_tls_scheme_deschedules():
    output = main.run(_meta("192.0.2.1", scheme="http"))

    assert output == [({"openkat/deschedule"}, "Skipping check due to non-TLS scheme")]
