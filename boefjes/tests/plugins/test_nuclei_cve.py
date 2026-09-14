import subprocess

import pytest

from boefjes.plugins.kat_nuclei_cve import main


def _meta(oci_args=None) -> dict:
    return {
        "arguments": {
            "input": {"name": "mispo.es"},
            "oci_arguments": oci_args or ["-t", "/root/nuclei-templates/http/cves/", "-jsonl"],
        }
    }


def _fake_run(returncode: int, stdout: bytes = b"", stderr: bytes = b""):
    def fake_run(cmd, capture_output):
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

    return fake_run


def test_nuclei_no_results_returns_empty(monkeypatch):
    """nuclei exits 1 with 'No results found' — not a real error."""
    stderr = b"[INF] No results found. Better luck next time!\n[FTL] Could not run nuclei: no templates provided for scan\n"
    monkeypatch.setattr(main.subprocess, "run", _fake_run(1, stderr=stderr))

    output = main.run(_meta())

    assert output == [({"openkat/nuclei-output"}, "")]


def test_nuclei_success_returns_stdout(monkeypatch):
    monkeypatch.setattr(main.subprocess, "run", _fake_run(0, stdout=b'{"id":"cve-2024-1"}\n'))

    output = main.run(_meta())

    assert output == [({"openkat/nuclei-output"}, '{"id":"cve-2024-1"}\n')]


def test_nuclei_real_error_still_raises(monkeypatch):
    """A non-zero exit without a benign marker is still a real error."""
    monkeypatch.setattr(main.subprocess, "run", _fake_run(2, stderr=b"unknown flag: --foo"))

    with pytest.raises(RuntimeError, match="nuclei exited with code 2"):
        main.run(_meta())
