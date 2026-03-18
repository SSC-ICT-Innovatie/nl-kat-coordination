import datetime
import os

import pytest

from boefjes.storage.interfaces import ConfigNotFound, OrganisationNotFound, PluginNotFound, StorageError
from boefjes.worker.models import Boefje, BoefjeConfig, Normalizer, Organisation

pytestmark = pytest.mark.skipif(os.environ.get("CI") != "1", reason="Needs a CI database.")


def test_organisation_storage(organisation_storage):
    organisation_id = "test"

    org = Organisation(id=organisation_id, name="Test")
    with organisation_storage as storage:
        storage.create(org)

    with organisation_storage as storage:
        returned_org = storage.get_by_id(organisation_id)
    assert org == returned_org

    with organisation_storage as storage:
        all_organisations = storage.get_all()

    assert org == all_organisations[organisation_id]

    with organisation_storage as storage:
        storage.delete_by_id(organisation_id)

    with pytest.raises(OrganisationNotFound), organisation_storage as storage:
        storage.get_by_id(organisation_id)


def test_settings_storage(plugin_storage, organisation_storage, config_storage):
    organisation_id = "test"
    plugin_id = 64 * "a"

    with plugin_storage as storage:
        storage.create_boefje(Boefje(id=plugin_id, name="Test"))

    org = Organisation(id=organisation_id, name="Test")
    with organisation_storage as storage:
        storage.create(org)

    with config_storage as settings_storage:
        settings_storage.upsert(organisation_id, plugin_id, {"TEST_SETTING": "123.9", "TEST_SETTING2": 12})

    with config_storage as settings_storage:
        settings_storage.upsert(organisation_id, plugin_id, {"TEST_SETTING": "123.9", "TEST_SETTING2": 13})
        returned_settings = settings_storage.get_all_settings(organisation_id, plugin_id)

    assert returned_settings["TEST_SETTING"] == "123.9"
    assert returned_settings["TEST_SETTING2"] == 13

    with pytest.raises(ConfigNotFound), config_storage:
        config_storage.delete("no organisation!", plugin_id)

    with config_storage as settings_storage:
        assert settings_storage.get_all_settings(org.id, plugin_id) == {"TEST_SETTING": "123.9", "TEST_SETTING2": 13}
        assert config_storage.get_all_settings(org.id, "wrong") == {}
        assert config_storage.get_all_settings("wrong", plugin_id) == {}

    with config_storage as settings_storage:
        settings_storage.delete(org.id, plugin_id)

    with config_storage as settings_storage:
        assert settings_storage.get_all_settings(org.id, plugin_id) == {}

    with pytest.raises(StorageError), config_storage as settings_storage:
        settings_storage.upsert(organisation_id, 65 * "a", {"TEST_SETTING": "123.9"})

    # Test getting configs
    org2 = Organisation(id="test2", name="Test2")
    with organisation_storage as storage:
        storage.create(org2)

    with config_storage as settings_storage:
        settings_storage.upsert(organisation_id, plugin_id, {"TEST_SETTING": "123.9", "TEST_SETTING2": 12})
        settings_storage.upsert(org2.id, plugin_id, {"TEST_SETTING2": 12, "TEST_SETTING": "123.9"})

    config1 = BoefjeConfig(
        id=6,
        settings={"TEST_SETTING": "123.9", "TEST_SETTING2": 12},
        enabled=False,
        boefje_id="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        organisation_id="test",
    )
    config2 = BoefjeConfig(
        id=7,
        settings={"TEST_SETTING": "123.9", "TEST_SETTING2": 12},
        enabled=False,
        boefje_id="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        organisation_id="test2",
    )
    config2_with_duplicates = config2.model_copy(update={"duplicates": [config1]})

    with config_storage as settings_storage:
        assert settings_storage.list_boefje_configs(0, 10) == [config1, config2]
        assert settings_storage.list_boefje_configs(1, 10) == [config2]
        assert settings_storage.list_boefje_configs(2, 10) == []
        assert settings_storage.list_boefje_configs(0, 1) == [config1]
        assert settings_storage.list_boefje_configs(0, 10, organisation_id=org2.id, with_duplicates=True) == [config2]
        assert settings_storage.list_boefje_configs(0, 10, organisation_id=org.id, with_duplicates=True) == [config1]
        assert settings_storage.list_boefje_configs(0, 10, enabled=True, with_duplicates=True) == []
        assert settings_storage.list_boefje_configs(0, 10, enabled=False, with_duplicates=True) == [config1, config2]
        assert settings_storage.list_boefje_configs(0, 10, boefje_id="b", with_duplicates=True) == []
        assert settings_storage.list_boefje_configs(
            0, 10, boefje_id=config2.boefje_id, organisation_id=org2.id, with_duplicates=True
        ) == [config2_with_duplicates]


def test_settings_storage_values_respect_field_limits(plugin_storage, organisation_storage, config_storage):
    organisation_id = "test"
    plugin_id = 64 * "a"

    with plugin_storage as storage:
        storage.create_boefje(Boefje(id=plugin_id, name="Test"))

    org = Organisation(id=organisation_id, name="Test")
    with organisation_storage as storage:
        storage.create(org)

    with config_storage as settings_storage:
        settings_storage.upsert(
            organisation_id,
            plugin_id,
            {
                "TEST_SETTING": 12 * "123.9",
                "TEST_SETTING2": 12000,
                "TEST_SETTING3": 30 * "b",
                "TEST_SETTING4": 30 * "b",
                "TEST_SETTING5": 10 * "b",
                "TEST_SETTING6": 123456789,
            },
        )

    with config_storage as settings_storage:
        assert settings_storage.get_all_settings(org.id, plugin_id) == {
            "TEST_SETTING": 12 * "123.9",
            "TEST_SETTING2": 12000,
            "TEST_SETTING3": 30 * "b",
            "TEST_SETTING4": 30 * "b",
            "TEST_SETTING5": 10 * "b",
            "TEST_SETTING6": 123456789,
        }


def test_plugin_enabled_storage(organisation_storage, plugin_storage, config_storage):
    with organisation_storage as storage:
        org = Organisation(id="test", name="Test")
        storage.create(org)

    plugin = Boefje(
        id="test-boefje-1",
        name="Test Boefje 1",
        version="0.1",
        consumes={"WebPage"},
        produces=["text/html"],
        enabled=True,
    )

    with plugin_storage as storage:
        storage.create_boefje(plugin)

    with config_storage as storage:
        storage.upsert(org.id, plugin.id, enabled=plugin.enabled)

    with config_storage as storage:
        returned_state = storage.is_enabled_by_id(plugin.id, org.id)
    assert returned_state is True

    with config_storage as storage:
        storage.upsert(org.id, plugin.id, enabled=False)

    with config_storage as storage:
        returned_state = storage.is_enabled_by_id(plugin.id, org.id)
    assert returned_state is False

    with pytest.raises(ConfigNotFound), config_storage as storage:
        storage.is_enabled_by_id("wrong", org.id)

    with pytest.raises(ConfigNotFound), config_storage as storage:
        storage.is_enabled_by_id("wrong", org.id)

    with pytest.raises(ConfigNotFound), config_storage as storage:
        storage.is_enabled_by_id(plugin.id, "wrong")


def test_bare_boefje_storage(plugin_storage):
    boefje = Boefje(id="test_boefje", name="Test", static=False)

    with plugin_storage as storage:
        storage.create_boefje(boefje)

    with plugin_storage as storage:
        returned_boefje = storage.boefje_by_id(boefje.id)
    assert boefje == returned_boefje

    with plugin_storage as storage:
        storage.update_boefje(boefje.id, {"description": "4"})

    with plugin_storage as storage:
        assert storage.boefje_by_id(boefje.id).description == "4"

    with plugin_storage as storage:
        storage.update_boefje(boefje.id, {"scan_level": 3})

    with plugin_storage as storage:
        assert storage.boefje_by_id(boefje.id).scan_level == 3

    boefje.description = "4"
    boefje.scan_level = 3

    with plugin_storage as storage:
        assert storage.boefje_by_id(boefje.id).description == "4"
    boefje.description = "4"

    with plugin_storage as storage:
        storage.update_boefje(boefje.id, {"scan_level": 3})

    with plugin_storage as storage:
        assert storage.boefje_by_id(boefje.id).scan_level == 3

    boefje.description = "4"
    boefje.scan_level = 3
    with plugin_storage as storage:
        all_plugins = storage.get_all()
    assert all_plugins == [boefje]

    with plugin_storage as storage:
        storage.delete_boefje_by_id(boefje.id)

    with pytest.raises(PluginNotFound), plugin_storage as storage:
        storage.boefje_by_id(boefje.id)


def test_rich_boefje_storage(plugin_storage):
    boefje = Boefje(
        id="test_boefje",
        name="Test",
        version="v1.09",
        created=datetime.datetime(2010, 10, 10, 10, 10, 10, tzinfo=datetime.UTC),
        description="My Boefje",
        scan_level=4,
        consumes=["Internet"],
        produces=[
            "image/png",
            "application/zip+json",
            "application/har+json",
            "application/json",
            "application/localstorage+json",
        ],
        oci_image="ghcr.io/test/image:123",
        oci_arguments=["host", "-n", "123123123123123123123"],
        static=False,
    )

    with plugin_storage as storage:
        storage.create_boefje(boefje)

    with plugin_storage as storage:
        returned_boefje = storage.boefje_by_id(boefje.id)

    assert boefje == returned_boefje


def test_bare_normalizer_storage(plugin_storage):
    normalizer = Normalizer(id="test_boefje", name="Test", static=False)

    with plugin_storage as storage:
        storage.create_normalizer(normalizer)

    with plugin_storage as storage:
        returned_normalizer = storage.normalizer_by_id(normalizer.id)
    assert normalizer == returned_normalizer

    with plugin_storage as storage:
        storage.update_normalizer(normalizer.id, {"version": "v4"})
    with plugin_storage as storage:
        assert storage.normalizer_by_id(normalizer.id).version == "v4"
    normalizer.version = "v4"

    with plugin_storage as storage:
        all_plugins = storage.get_all()
    assert all_plugins == [normalizer]

    with plugin_storage as storage:
        storage.delete_normalizer_by_id(normalizer.id)

    with pytest.raises(PluginNotFound), plugin_storage as storage:
        storage.normalizer_by_id(normalizer.id)


def test_rich_normalizer_storage(plugin_storage):
    normalizer = Normalizer(
        id="test_normalizer",
        name="Test",
        version="v1.19",
        created=datetime.datetime(2010, 10, 10, 10, 10, 10, tzinfo=datetime.UTC),
        description="My Normalizer",
        scan_level=4,
        consumes=["Internet"],
        produces=[
            "image/png",
            "application/zip+json",
            "application/har+json",
            "application/json",
            "application/localstorage+json",
        ],
        static=False,
    )

    with plugin_storage as storage:
        storage.create_normalizer(normalizer)
    with plugin_storage as storage:
        returned_normalizer = storage.normalizer_by_id(normalizer.id)

    assert normalizer == returned_normalizer


def test_plugin_storage(plugin_storage):
    boefje = Boefje(id="test_boefje", name="Test", static=False)
    normalizer = Normalizer(id="test_boefje", name="Test", static=False)

    with plugin_storage as storage:
        storage.create_boefje(boefje)
        storage.create_normalizer(normalizer)

    with plugin_storage as storage:
        assert storage.get_all() == [boefje, normalizer]
