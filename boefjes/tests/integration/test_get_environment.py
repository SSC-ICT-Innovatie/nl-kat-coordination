import pytest

from boefjes.clients.scheduler_client import get_environment_settings
from boefjes.dependencies.plugins import PluginService
from boefjes.worker.models import Organisation
from tests.loading import get_boefje_meta


@pytest.mark.skipif("os.environ.get('CI') != '1'")
def test_environment_builds_up_correctly(plugin_service: PluginService, organisation: Organisation):
    plugin_id = "dns-records"
    with plugin_service:
        schema = plugin_service.schema(plugin_id)
    environment = get_environment_settings(get_boefje_meta(boefje_id=plugin_id), schema)

    assert environment == {}

    with plugin_service:
        plugin_service.upsert_settings({"RECORD_TYPES": "CNAME,AAAA", "WRONG": "3"}, organisation.id, plugin_id)

    environment = get_environment_settings(get_boefje_meta(boefje_id=plugin_id), schema)

    assert environment == {"RECORD_TYPES": "CNAME,AAAA"}
