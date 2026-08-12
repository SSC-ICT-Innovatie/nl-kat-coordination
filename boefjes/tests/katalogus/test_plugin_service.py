import pytest

from boefjes.storage.interfaces import SettingsNotConformingToSchema


def test_get_plugins(mock_plugin_service, test_organisation):
    plugins = mock_plugin_service.get_all(test_organisation.id)
    assert len(plugins) == 15

    kat_test = list(filter(lambda x: x.id == "kat_test", plugins)).pop()
    assert kat_test.id == "kat_test"
    assert kat_test.name == "Kat test name"
    assert kat_test.consumes == {"DNSZone"}
    assert set(kat_test.produces) == {"boefje/kat_test"}

    kat_test_norm = list(filter(lambda x: x.id == "kat_test_normalize", plugins)).pop()
    assert "kat_test_normalize" in kat_test_norm.id
    assert kat_test_norm.consumes == ["text/html", "normalizer/kat_test_normalize"]
    assert kat_test_norm.produces == []


def test_get_plugin_by_id(mock_plugin_service, test_organisation):
    plugin = mock_plugin_service.by_plugin_id("kat_test_normalize", test_organisation.id)

    assert plugin.id == "kat_test_normalize"
    assert plugin.enabled is True


def test_update_by_id(mock_plugin_service, test_organisation):
    mock_plugin_service.set_enabled_by_id("kat_test_normalize", test_organisation.id, False)
    plugin = mock_plugin_service.by_plugin_id("kat_test_normalize", test_organisation.id)
    assert plugin.enabled is False


def test_update_by_id_bad_schema(mock_plugin_service, test_organisation):
    plugin_id = "kat_test"

    mock_plugin_service.config_storage.upsert(test_organisation.id, plugin_id, {"api_key": 128 * "a"})
    mock_plugin_service.set_enabled_by_id(plugin_id, test_organisation.id, True)

    with pytest.raises(SettingsNotConformingToSchema) as ctx:
        mock_plugin_service.upsert_settings({"api_key": 129 * "a"}, test_organisation.id, plugin_id)

    msg = f"Settings for plugin kat_test are not conform the plugin schema: '{129 * 'a'}' is too long"
    assert ctx.value.message == msg


def test_get_schema(mock_plugin_service):
    schema = mock_plugin_service.schema("kat_test")
    assert schema == {
        "title": "Arguments",
        "type": "object",
        "properties": {"api_key": {"title": "Api Key", "maxLength": 128, "type": "string"}},
        "required": ["api_key"],
    }

    schema = mock_plugin_service.schema("kat_test_normalize")
    assert schema is None


def test_removing_mandatory_setting_does_not_disable_plugin_anymore(mock_plugin_service, test_organisation):
    plugin_id = "kat_test"

    mock_plugin_service.config_storage.upsert(test_organisation.id, plugin_id, {"api_key": 128 * "a"})
    mock_plugin_service.set_enabled_by_id(plugin_id, test_organisation.id, True)

    plugin = mock_plugin_service.by_plugin_id(plugin_id, test_organisation.id)
    assert plugin.enabled is True

    mock_plugin_service.delete_settings(test_organisation.id, plugin_id)

    plugin = mock_plugin_service.by_plugin_id(plugin_id, test_organisation.id)
    assert plugin.enabled is True


def test_adding_integer_settings_within_given_constraints(mock_plugin_service, test_organisation):
    plugin_id = "kat_test_2"

    with pytest.raises(SettingsNotConformingToSchema) as ctx:
        mock_plugin_service.upsert_settings({"api_key": "24"}, test_organisation.id, plugin_id)

    assert "'24' is not of type 'integer'" in ctx.value.message

    mock_plugin_service.upsert_settings({"api_key": 24}, test_organisation.id, plugin_id)
    mock_plugin_service.set_enabled_by_id(plugin_id, test_organisation.id, True)

    plugin = mock_plugin_service.by_plugin_id(plugin_id, test_organisation.id)
    assert plugin.enabled is True
    mock_plugin_service.set_enabled_by_id(plugin_id, test_organisation.id, False)


def test_clone_one_setting(mock_plugin_service, test_organisation):
    new_org_id = "org2"
    plugin_id = "kat_test"
    mock_plugin_service.config_storage.upsert(test_organisation.id, plugin_id, {"api_key": "24"})
    assert mock_plugin_service.get_all_settings(test_organisation.id, plugin_id) == {"api_key": "24"}

    mock_plugin_service.set_enabled_by_id(plugin_id, test_organisation.id, True)

    assert "api_key" not in mock_plugin_service.get_all_settings(new_org_id, plugin_id)

    new_org_plugins = mock_plugin_service.get_all(new_org_id)
    assert len(new_org_plugins) == 15
    assert len([x for x in new_org_plugins if x.enabled]) == 5  # 2 Normalizers
    assert plugin_id not in [x.id for x in new_org_plugins if x.enabled]

    mock_plugin_service.clone_settings_to_organisation(test_organisation.id, new_org_id)

    assert mock_plugin_service.get_all_settings(test_organisation.id, plugin_id) == {"api_key": "24"}
    assert mock_plugin_service.get_all_settings(new_org_id, plugin_id) == {"api_key": "24"}

    new_org_plugins = mock_plugin_service.get_all(new_org_id)
    assert len(new_org_plugins) == 15
    assert len([x for x in new_org_plugins if x.enabled]) == 6  # 2 Normalizers, 1 boefje
    assert plugin_id in [x.id for x in new_org_plugins if x.enabled]


def test_clone_many_settings(mock_plugin_service, test_organisation):
    plugin_id_1 = "kat_test"

    all_settings_1 = {"api_key": "123"}
    mock_plugin_service.upsert_settings(all_settings_1, test_organisation.id, plugin_id_1)
    mock_plugin_service.clone_settings_to_organisation(test_organisation.id, "org2")

    all_settings_for_new_org = mock_plugin_service.get_all_settings("org2", plugin_id_1)
    assert len(all_settings_for_new_org) == 1
    assert all_settings_for_new_org == {"api_key": "123"}
