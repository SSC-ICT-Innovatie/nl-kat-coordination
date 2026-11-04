import subprocess
import time

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


def _meta(ip: str, port: int = 443, service_name: str = "https", input_type: str = "HostnameIPService") -> dict:
    input_: dict = {
        "object_type": input_type,
        "ip_service": {"service": {"name": service_name}, "ip_port": {"address": {"address": ip}, "port": port}},
    }
    if input_type != "IPService":
        input_["hostname"] = {"name": "example.com"}
    return {"arguments": {"input": input_, "oci_arguments": ["s_client", "-prexit", "-showcerts"]}}


def _fake_run(returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""):
    def fake_run(cmd, capture_output=False, timeout=None):
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

    return fake_run


def test_ipv6_address_not_bracketed(monkeypatch):
    """s_client -host takes the bare address: bracketed IPv6 makes
    BIO_lookup_ex fail with 'Name or service not known' (OpenSSL 3.5.7)."""
    captured = {}

    def fake_run(cmd, capture_output=False, timeout=None):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=PEM_OUTPUT, stderr=b"")

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    main.run(_meta("2001:db8::1"))

    idx = captured["cmd"].index("-host")
    assert captured["cmd"][idx + 1] == "2001:db8::1"


def test_ipv4_address_not_wrapped(monkeypatch):
    captured = {}

    def fake_run(cmd, capture_output=False, timeout=None):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=PEM_OUTPUT, stderr=b"")

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    main.run(_meta("192.0.2.1"))

    idx = captured["cmd"].index("-host")
    assert captured["cmd"][idx + 1] == "192.0.2.1"


def test_sni_sent_for_hostname_input(monkeypatch):
    captured = {}

    def fake_run(cmd, capture_output=False, timeout=None):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=PEM_OUTPUT, stderr=b"")

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    main.run(_meta("192.0.2.1"))

    idx = captured["cmd"].index("-servername")
    assert captured["cmd"][idx + 1] == "example.com"


def test_no_sni_for_ip_service_input(monkeypatch):
    """A bare IPService input is a connection without a server name."""
    captured = {}

    def fake_run(cmd, capture_output=False, timeout=None):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=PEM_OUTPUT, stderr=b"")

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    main.run(_meta("192.0.2.1", input_type="IPService"))

    assert "-servername" not in captured["cmd"]


def test_sni_still_sent_for_legacy_website_input(monkeypatch):
    """Until the consumes list flips, the boefje is scheduled with Website
    inputs; those must keep their SNI unchanged."""
    captured = {}

    def fake_run(cmd, capture_output=False, timeout=None):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=PEM_OUTPUT, stderr=b"")

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    main.run(_meta("192.0.2.1", input_type="Website"))

    idx = captured["cmd"].index("-servername")
    assert captured["cmd"][idx + 1] == "example.com"


def test_failure_records_output(monkeypatch):
    """A failed handshake records the raw output (empty stdout, but the
    task succeeds): the reason lives in Bytes with the task, nothing
    retries."""
    monkeypatch.setattr(main.subprocess, "run", _fake_run(1, stderr=b"connect:errno=101\nNetwork unreachable\n"))

    output = main.run(_meta("192.0.2.1"))

    assert output == [({"openkat/ssl-certificates-output"}, "")]


def test_nonzero_exit_with_certificates_returns_output(monkeypatch):
    """A failed TLS handshake still yields the certificate chain (#5417)."""
    monkeypatch.setattr(main.subprocess, "run", _fake_run(1, stdout=PEM_OUTPUT, stderr=b"handshake failure"))

    output = main.run(_meta("192.0.2.1"))

    assert output == [({"openkat/ssl-certificates-output"}, PEM_OUTPUT.decode())]


def test_non_tls_service_returns_raw_output(monkeypatch):
    """A service that does not do TLS yields its raw openssl output: the
    failure reason lives in the output, the normalizer reads no PEM and
    observes nothing. No crash, no deschedule, no retry storm."""
    monkeypatch.setattr(main.subprocess, "run", _fake_run(1, stderr=b"connect:errno=104\nConnection reset by peer\n"))

    output = main.run(_meta("192.0.2.1", service_name="http"))

    assert output == [({"openkat/ssl-certificates-output"}, "")]


def test_tcpwrapped_service_is_attempted(monkeypatch):
    captured = {}

    def fake_run(cmd, capture_output=False, timeout=None):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 1, stdout=b"", stderr=b"alert handshake failure")

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    output = main.run(_meta("192.0.2.1", service_name="tcpwrapped"))

    assert "-host" in captured["cmd"]
    assert output == [({"openkat/ssl-certificates-output"}, "")]


def test_blackholed_address_returns_partial_output_within_timeout(monkeypatch):
    """A silent blackhole (no SYN-ACK, no response) must not hang the
    worker: subprocess.TimeoutExpired is raised, and the partial output is
    recorded."""

    def hanging_run(cmd, capture_output=False, timeout=None):
        time.sleep(timeout + 0.1)  # outlive the boefje timeout
        raise subprocess.TimeoutExpired(cmd, timeout, output=b"partial output before hang")

    monkeypatch.setattr(main.subprocess, "run", hanging_run)
    monkeypatch.setattr(main, "BOEFJE_TIMEOUT_SECONDS", 1)

    started = time.monotonic()
    output = main.run(_meta("192.0.2.1"))
    elapsed = time.monotonic() - started

    assert elapsed < 5  # bounded: did not wait for the fake 60s hang
    assert output == [({"openkat/ssl-certificates-output"}, "partial output before hang")]


def test_tls_capable_service_names_are_attempted(monkeypatch):
    """imaps, smtps, ftps, ldaps and unknown names are all attempted: a
    service on any port may do TLS."""
    calls = []

    def fake_run(cmd, capture_output=False, timeout=None):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=PEM_OUTPUT, stderr=b"")

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    for service_name in ("imaps", "smtps", "ftps", "ldaps", "some-future-tls-service"):
        output = main.run(_meta("192.0.2.1", service_name=service_name))
        # attempted and returned, not descheduled
        assert output[0][0] == {"openkat/ssl-certificates-output"}
        assert "-host 192.0.2.1" in " ".join(output and calls[-1])
    assert len(calls) == 5
