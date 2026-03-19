from django.urls import reverse
from katalogus.views.plugin_settings_add import PluginSettingsAddView
from pytest_django.asserts import assertContains, assertNotContains

from tests.conftest import setup_request


def test_plugin_settings_add_view(rf, superuser_member, mock_mixins_katalogus, plugin_details, plugin_schema):
    mock_mixins_katalogus.get_plugin.return_value = plugin_details
    mock_mixins_katalogus.get_plugin_schema.return_value = plugin_schema

    request = setup_request(rf.get("plugin_settings_add"), superuser_member.user)
    response = PluginSettingsAddView.as_view()(
        request, organization_code=superuser_member.organization.code, plugin_type="boefje", plugin_id="test-plugin"
    )

    assertContains(response, "TestBoefje")
    assertContains(response, "Add setting")
    assertContains(response, "TEST_PROPERTY")
    assertContains(response, "TEST_PROPERTY2")
    assertContains(response, "Add settings and enable boefje")


def test_plugin_settings_add_view_no_required(
    rf, superuser_member, mock_mixins_katalogus, plugin_details, plugin_schema_no_required
):
    mock_mixins_katalogus.get_plugin.return_value = plugin_details
    mock_mixins_katalogus.get_plugin_schema.return_value = plugin_schema_no_required

    request = setup_request(rf.get("plugin_settings_add"), superuser_member.user)
    response = PluginSettingsAddView.as_view()(
        request, organization_code=superuser_member.organization.code, plugin_type="boefje", plugin_id="test-plugin"
    )

    assertContains(response, "TestBoefje")
    assertContains(response, "Add setting")
    assertContains(response, "TEST_PROPERTY")
    assertContains(response, "TEST_PROPERTY2")
    assertContains(response, "Add settings and enable boefje")


def test_plugin_settings_add(rf, superuser_member, mock_mixins_katalogus, plugin_details, plugin_schema):
    mock_mixins_katalogus.get_plugin.return_value = plugin_details
    mock_mixins_katalogus.get_plugin_schema.return_value = plugin_schema
    mock_mixins_katalogus.get_plugin_settings.return_value = {"TEST_PROPERTY": "abc"}

    request = setup_request(rf.post("plugin_settings_add", data={"TEST_PROPERTY": "123"}), superuser_member.user)
    response = PluginSettingsAddView.as_view()(
        request, organization_code=superuser_member.organization.code, plugin_type="boefje", plugin_id="test-plugin"
    )

    assert response.status_code == 302
    assert list(request._messages).pop().message == "Added settings for 'TestBoefje'"


def test_plugin_settings_add_no_required(
    rf, superuser_member, mock_mixins_katalogus, plugin_details, plugin_schema_no_required
):
    mock_mixins_katalogus.get_plugin.return_value = plugin_details
    mock_mixins_katalogus.get_plugin_schema.return_value = plugin_schema_no_required
    mock_mixins_katalogus.get_plugin_settings.return_value = {"TEST_PROPERTY": "abc"}

    request = setup_request(rf.post("plugin_settings_add", data={"TEST_PROPERTY": "123"}), superuser_member.user)
    response = PluginSettingsAddView.as_view()(
        request, organization_code=superuser_member.organization.code, plugin_type="boefje", plugin_id="test-plugin"
    )

    assert response.status_code == 302
    assert list(request._messages).pop().message == "Added settings for 'TestBoefje'"


def test_plugin_settings_add_wrong_property_but_required(
    rf, superuser_member, mock_mixins_katalogus, plugin_details, plugin_schema
):
    mock_mixins_katalogus.get_plugin.return_value = plugin_details
    mock_mixins_katalogus.get_plugin_schema.return_value = plugin_schema
    mock_mixins_katalogus.get_plugin_settings.return_value = {"TEST_PROPERTY": "abc"}

    request = setup_request(rf.post("plugin_settings_add", data={"WRONG_PROPERTY": 123}), superuser_member.user)
    response = PluginSettingsAddView.as_view()(
        request, organization_code=superuser_member.organization.code, plugin_type="boefje", plugin_id="test-plugin"
    )
    assertContains(response, "Error")
    assertContains(response, "This field is required.")


def test_plugin_settings_add_string_too_long(
    rf, superuser_member, mock_mixins_katalogus, plugin_details, plugin_schema
):
    mock_mixins_katalogus.get_plugin.return_value = plugin_details
    mock_mixins_katalogus.get_plugin_schema.return_value = plugin_schema
    mock_mixins_katalogus.get_plugin_settings.return_value = {"TEST_PROPERTY": "abc"}

    request = setup_request(rf.post("plugin_settings_add", data={"TEST_PROPERTY": 129 * "a"}), superuser_member.user)
    response = PluginSettingsAddView.as_view()(
        request, organization_code=superuser_member.organization.code, plugin_type="boefje", plugin_id="test-plugin"
    )
    assertContains(response, "Ensure this value has at most 128 characters (it has 129).")
    assertNotContains(response, "Enter a whole number.")


def test_plugin_settings_add_error_message_about_integer_for_string_type(
    rf, superuser_member, mock_mixins_katalogus, plugin_details, plugin_schema
):
    mock_mixins_katalogus.get_plugin.return_value = plugin_details
    mock_mixins_katalogus.get_plugin_schema.return_value = plugin_schema

    request = setup_request(
        rf.post("plugin_settings_add", data={"TEST_PROPERTY": "abc", "TEST_PROPERTY2": "abc"}), superuser_member.user
    )
    response = PluginSettingsAddView.as_view()(
        request, organization_code=superuser_member.organization.code, plugin_type="boefje", plugin_id="test-plugin"
    )

    assertContains(response, "Error")
    assertContains(response, "Enter a whole number.")


def test_plugin_settings_add_error_message_about_integer_too_small(
    rf, superuser_member, mock_mixins_katalogus, plugin_details, plugin_schema
):
    mock_mixins_katalogus.get_plugin.return_value = plugin_details
    mock_mixins_katalogus.get_plugin_schema.return_value = plugin_schema

    request = setup_request(
        rf.post("plugin_settings_add", data={"TEST_PROPERTY": "abc", "TEST_PROPERTY2": 1}), superuser_member.user
    )
    response = PluginSettingsAddView.as_view()(
        request, organization_code=superuser_member.organization.code, plugin_type="boefje", plugin_id="test-plugin"
    )

    assertContains(response, "Error")
    assertContains(response, "1 is less than the minimum of 2")


def test_plugin_settings_add_error_message_about_integer_too_big(
    rf, superuser_member, mock_mixins_katalogus, plugin_details, plugin_schema
):
    mock_mixins_katalogus.get_plugin.return_value = plugin_details
    mock_mixins_katalogus.get_plugin_schema.return_value = plugin_schema

    request = setup_request(
        rf.post("plugin_settings_add", data={"TEST_PROPERTY": "abc", "TEST_PROPERTY2": 1000}), superuser_member.user
    )
    response = PluginSettingsAddView.as_view()(
        request, organization_code=superuser_member.organization.code, plugin_type="boefje", plugin_id="test-plugin"
    )

    assertContains(response, "Error")
    assertContains(response, "1000 is greater than the maximum of 200")


def test_plugin_single_settings_add_view_no_schema(rf, superuser_member, mock_mixins_katalogus, plugin_details):
    plugin_details.boefje_schema = None
    mock_mixins_katalogus.get_plugin.return_value = plugin_details
    mock_mixins_katalogus.get_plugin_settings.return_value = None

    request = setup_request(rf.post("plugin_settings_add", data={"boefje_id": 123}), superuser_member.user)
    response = PluginSettingsAddView.as_view()(
        request, organization_code=superuser_member.organization.code, plugin_type="boefje", plugin_id="test-plugin"
    )

    assert response.status_code == 302
    mock_mixins_katalogus.upsert_plugin_settings.assert_not_called()

    assert response.headers["Location"] == reverse(
        "boefje_detail", kwargs={"organization_code": superuser_member.organization.code, "plugin_id": "test-boefje"}
    )
    assert list(request._messages).pop().message == "Trying to add settings to boefje without schema"
