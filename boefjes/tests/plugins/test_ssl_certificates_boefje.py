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


def _meta(ip: str, port: int = 443, scheme: str = "https") -> dict:
    return {
        "arguments": {
            "input": {
                "hostname": {"name": "example.com"},
                "ip_service": {"service": {"name": scheme}, "ip_port": {"address": {"address": ip}, "port": port}},
            },
            "oci_arguments": ["s_client", "-prexit", "-showcerts"],
        }
    }


def _fake_run(returncode: int, stdout: bytes = b"", stderr: bytes = b""):
    def fake_run(cmd, capture_output):
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

    return fake_run


def test_success_returns_stdout(monkeypatch):
    monkeypatch.setattr(main.subprocess, "run", _fake_run(0, stdout=b"cert data here"))

    output = main.run(_meta("192.0.2.1"))

    assert output == [({"openkat/ssl-certificates-output"}, "cert data here")]


def test_nonzero_exit_with_certificates_returns_output(monkeypatch):
    """A failed TLS handshake still yields the certificate chain (#5417)."""
    monkeypatch.setattr(main.subprocess, "run", _fake_run(1, stdout=PEM_OUTPUT, stderr=b"handshake failure"))

    output = main.run(_meta("192.0.2.1"))

    assert output == [({"openkat/ssl-certificates-output"}, PEM_OUTPUT.decode())]


def test_nonzero_exit_without_certificates_crashes_task(monkeypatch):
    """A transient failure yields no output: crash so the scheduler retries."""
    monkeypatch.setattr(main.subprocess, "run", _fake_run(1, stderr=b"connect:errno=101\nNetwork unreachable\n"))

    with pytest.raises(subprocess.CalledProcessError):
        main.run(_meta("192.0.2.1"))


def test_non_tls_scheme_deschedules():
    output = main.run(_meta("192.0.2.1", scheme="http"))

    assert output == [({"openkat/deschedule"}, "Skipping check due to non-TLS scheme")]
