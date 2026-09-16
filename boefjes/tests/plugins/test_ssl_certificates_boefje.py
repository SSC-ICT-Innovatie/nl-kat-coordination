import subprocess

import pytest

from boefjes.plugins.kat_ssl_certificates import main


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


def test_ipv6_address_wrapped_in_brackets(monkeypatch):
    captured = {}

    def fake_run(cmd, capture_output):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=b"cert output", stderr=b"")

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    main.run(_meta("2001:610:2d8:401::33:18"))

    assert "-host" in captured["cmd"]
    idx = captured["cmd"].index("-host")
    assert captured["cmd"][idx + 1] == "[2001:610:2d8:401::33:18]"


def test_ipv4_address_not_wrapped(monkeypatch):
    captured = {}

    def fake_run(cmd, capture_output):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=b"cert output", stderr=b"")

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    main.run(_meta("192.0.2.1"))

    idx = captured["cmd"].index("-host")
    assert captured["cmd"][idx + 1] == "192.0.2.1"


def test_network_error_crashes_task(monkeypatch):
    monkeypatch.setattr(main.subprocess, "run", _fake_run(1, stderr=b"connect:errno=101\nNetwork unreachable\n"))

    with pytest.raises(subprocess.CalledProcessError):
        main.run(_meta("2001:610:2d8:401::33:18"))


def test_success_returns_stdout(monkeypatch):
    monkeypatch.setattr(main.subprocess, "run", _fake_run(0, stdout=b"cert data here"))

    output = main.run(_meta("192.0.2.1"))

    assert output == [({"openkat/ssl-certificates-output"}, "cert data here")]


def test_non_tls_scheme_deschedules(monkeypatch):
    output = main.run(_meta("192.0.2.1", scheme="http"))

    assert output == [({"openkat/deschedule"}, "Skipping check due to non-TLS scheme")]
