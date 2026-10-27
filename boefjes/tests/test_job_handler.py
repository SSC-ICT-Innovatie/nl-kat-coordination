import json
from pathlib import Path
from unittest.mock import patch

import pytest
from jsonschema.exceptions import ValidationError

from boefjes.clients.scheduler_client import (
    boefje_env_variables,
    get_environment_settings,
    get_system_env_settings_for_boefje,
)
from tests.loading import get_boefje_meta

NMAP_SCHEMA = json.loads((Path(__file__).parent.parent / "boefjes/plugins/kat_nmap_tcp/schema.json").read_text())
BOOL_SCHEMA = {"type": "object", "properties": {"FLAG": {"type": "boolean"}}}


def _environment_settings(monkeypatch, key, value, schema):
    boefje_env_variables.cache_clear()
    monkeypatch.setenv(f"BOEFJE_{key}", value)

    with patch("boefjes.clients.scheduler_client.httpx") as mock_httpx:
        mock_httpx.get.return_value.json.return_value = {}
        mock_httpx.get.return_value.raise_for_status.return_value = None

        return get_environment_settings(get_boefje_meta(boefje_id="nmap"), schema)


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
        "properties": {"PORTS": {"type": "string"}, "MIN_VLSM_IPV4": {"type": "integer", "minimum": 0, "maximum": 32}},
        "required": ["PORTS"],
    }

    with patch("boefjes.clients.scheduler_client.httpx") as mock_httpx:
        mock_httpx.get.return_value.json.return_value = {"PORTS": "80,443"}
        mock_httpx.get.return_value.raise_for_status.return_value = None

        env = get_environment_settings(get_boefje_meta(boefje_id="nmap-ports"), schema)

    assert env["MIN_VLSM_IPV4"] == "24"
    assert env["PORTS"] == "80,443"


def test_top_ports_env_var_is_coerced_for_real_nmap_schema(monkeypatch):
    assert _environment_settings(monkeypatch, "TOP_PORTS", "50", NMAP_SCHEMA)["TOP_PORTS"] == "50"


def test_invalid_integer_env_var_raises_validation_error(monkeypatch):
    with pytest.raises(ValidationError):
        _environment_settings(monkeypatch, "TOP_PORTS", "abc", NMAP_SCHEMA)


@pytest.mark.parametrize("value", ["true", "1", "yes", "false", "0", "no", " True "])
def test_recognised_boolean_env_var_is_accepted(monkeypatch, value):
    expected = str(value.strip().lower() in ("true", "1", "yes"))

    assert _environment_settings(monkeypatch, "FLAG", value, BOOL_SCHEMA)["FLAG"] == expected


def test_unrecognised_boolean_env_var_is_rejected(monkeypatch):
    with pytest.raises(ValidationError):
        _environment_settings(monkeypatch, "FLAG", "maybe", BOOL_SCHEMA)
