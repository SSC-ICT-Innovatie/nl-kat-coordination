from boefjes.clients.scheduler_client import boefje_env_variables, get_system_env_settings_for_boefje


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
