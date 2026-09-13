from unittest.mock import patch

from boefjes.clients.scheduler_client import (
    boefje_env_variables,
    get_environment_settings,
    get_system_env_settings_for_boefje,
)
from boefjes.worker.job_models import BoefjeMeta
from tests.loading import get_boefje_meta


def test_boefje_systems_vars(monkeypatch):
    boefje_env_variables.cache_clear()

    monkeypatch.setenv("BOEFJE_TEST1", "Test")

    env = get_system_env_settings_for_boefje(["TEST1", "TEST2"])

    assert env == {"TEST1": "Test"}


def test_boefje_system_vars_no_vars():
    boefje_env_variables.cache_clear()

    env = get_system_env_settings_for_boefje(["TEST1", "TEST2"])

    assert env == {}


def test_boefje_systems_vars_no_allowed_keys(monkeypatch):
    boefje_env_variables.cache_clear()

    monkeypatch.setenv("BOEFJE_TEST1", "Test")

    env = get_system_env_settings_for_boefje([])

    assert env == {}


def test_environment_settings_coerces_integer_env_var(monkeypatch):
    """Env vars are strings, but an integer schema field should accept them (#3827)."""
    boefje_env_variables.cache_clear()
    monkeypatch.setenv("BOEFJE_MIN_VLSM_IPV4", "24")

    schema = {
        "type": "object",
        "properties": {
            "PORTS": {"type": "string"},
            "MIN_VLSM_IPV4": {"type": "integer", "minimum": 0, "maximum": 32},
        },
        "required": ["PORTS"],
    }

    with patch("boefjes.clients.scheduler_client.httpx") as mock_httpx:
        mock_httpx.get.return_value.json.return_value = {"PORTS": "80,443"}
        mock_httpx.get.return_value.raise_for_status.return_value = None

        env = get_environment_settings(get_boefje_meta(boefje_id="nmap-ports"), schema)

    assert env["MIN_VLSM_IPV4"] == "24"
    assert env["PORTS"] == "80,443"
