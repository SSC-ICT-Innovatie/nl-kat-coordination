import stat
from pathlib import Path
from unittest import mock

from boefjes.plugins.kat_cve_2023_34039.main import KEYS_DIR, run


def _meta(service: str = "ssh") -> dict:
    return {
        "arguments": {
            "input": {"service": {"name": service}, "ip_port": {"address": {"address": "1.2.3.4"}, "port": 22}}
        }
    }


def test_skips_non_ssh_service():
    assert run(_meta(service="http")) == [({"openkat/deschedule"}, "Skipping because service is not an ssh service")]


def test_keys_dir_resolves_to_the_bundled_keys():
    # os.walk("keys") used the wrong CWD and found nothing; the module-relative
    # KEYS_DIR must contain the 22 bundled vRNI keys.
    keys = [p for p in KEYS_DIR.rglob("*") if p.is_file()]
    assert len(keys) == 22


def test_reports_finding_with_a_private_key_copy_when_a_key_is_accepted():
    captured = {}

    def fake_run(cmd, **kwargs):
        key_path = cmd[cmd.index("-i") + 1]
        captured["mode"] = stat.S_IMODE(Path(key_path).stat().st_mode)
        return mock.Mock(returncode=0)

    with mock.patch("boefjes.plugins.kat_cve_2023_34039.main.subprocess.run", side_effect=fake_run):
        out = run(_meta())

    assert ({"openkat/finding"}, "CVE-2023-34039") in out
    # ssh was handed a 0600 key copy, so OpenSSH no longer refuses it.
    assert captured["mode"] == 0o600


def test_reports_not_vulnerable_when_all_keys_are_rejected():
    with mock.patch("boefjes.plugins.kat_cve_2023_34039.main.subprocess.run", return_value=mock.Mock(returncode=255)):
        assert run(_meta()) == [(set(), "No known keys allowed")]
