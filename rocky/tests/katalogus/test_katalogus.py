import pytest
from django.core.exceptions import PermissionDenied
from django.urls import resolve
from katalogus.client import (
    KATalogusClient,
    KATalogusNotAllowedError,
    parse_plugin,
    valid_organization_code,
    valid_plugin_id,
)
from katalogus.views.katalogus import AboutPluginsView, BoefjeListView, KATalogusView, NormalizerListView
from katalogus.views.katalogus_settings import ConfirmCloneSettingsView, KATalogusSettingsView
from katalogus.views.plugin_enable_disable import PluginEnableDisableView
from pytest_django.asserts import assertContains, assertNotContains

from rocky.health import ServiceHealth
from tests.conftest import (
    add_redteam_group_permissions,
    create_member,
    get_boefjes_data,
    get_normalizers_data,
    get_plugins_data,
    setup_request,
)


def test_valid_plugin_id():
    with pytest.raises(ValueError):
        valid_plugin_id("test test")

    with pytest.raises(ValueError):
        valid_plugin_id("test$test")

    assert valid_plugin_id("123") == "123"
    assert valid_plugin_id("test-test") == "test-test"


def test_valid_organization_code():
    with pytest.raises(ValueError):
        valid_organization_code("123 123")

    assert valid_organization_code("test-test") == "test-test"


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_katalogus_plugin_listing(request, rf, member, mocker):
    plugins = get_plugins_data()
    mock_requests = mocker.patch("katalogus.client.httpx")
    mock_response = mocker.MagicMock()
    mock_requests.Client().get.return_value = mock_response
    mock_response.json.return_value = plugins
    member = request.getfixturevalue(member)

    request = setup_request(rf.get("all_plugins_list"), member.user)
    request.resolver_match = mocker.Mock(url_name="all_plugins_list")
    response = KATalogusView.as_view()(request, organization_code=member.organization.code)
    assert response.status_code == 200
    assertContains(response, "KAT-alogus")
    assertContains(response, "An overview of all available plugins.")

    # active toolbar, only one link is active, "All"
    assertContains(
        response,
        '<li aria-current="page"><a href="/en/'
        + member.organization.code
        + '/kat-alogus/plugins/all/grid/">All</a></li>',
        html=True,
    )
    assertNotContains(
        response,
        '<li aria-current="page"><a href="/en/' + member.organization.code + '/kat-alogus/">Boefjes</a></li>',
        html=True,
    )
    assertNotContains(
        response,
        '<li aria-current="page"><a href="/en/' + member.organization.code + '/kat-alogus/">Normalizers</a></li>',
        html=True,
    )
    assertNotContains(
        response,
        '<li aria-current="page"><a href="/en/' + member.organization.code + '/kat-alogus/">About plugins</a></li>',
        html=True,
    )

    assertContains(response, f"<strong>{len(plugins)}</strong>Plugins available", html=True)

    # All plugins shows Boefjes and Normalizers, checking if one of each is available
    assertContains(response, "kat_adr_finding_types_normalize")
    assertContains(response, '<span class="label-plugin-type normalizer">Normalizer</span>')

    assertContains(response, "binaryedge")
    assertContains(response, '<span class="label-plugin-type boefje">Boefje</span>')


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_katalogus_plugin_listing_boefjes(request, rf, member, mocker):
    boefjes = get_boefjes_data()
    mock_requests = mocker.patch("katalogus.client.httpx")
    mock_response = mocker.MagicMock()
    mock_requests.Client().get.return_value = mock_response
    mock_response.json.return_value = boefjes
    member = request.getfixturevalue(member)

    request = setup_request(rf.get("boefjes_list"), member.user)
    request.resolver_match = mocker.Mock(url_name="boefjes_list")
    response = BoefjeListView.as_view()(request, organization_code=member.organization.code)

    assert response.status_code == 200
    assertContains(response, "Boefjes")
    assertContains(
        response,
        '<li aria-current="page"><a href="/en/'
        + member.organization.code
        + '/kat-alogus/plugins/boefjes/grid/">Boefjes</a></li>',
        html=True,
    )
    assertContains(response, f"<strong>{len(boefjes)}</strong>Boefjes available", html=True)
    assertNotContains(response, '<span class="label-plugin-type normalizer">Normalizer</span>')
    assertContains(response, '<span class="label-plugin-type boefje">Boefje</span>')
    assertContains(response, "ssl-certificates")


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_katalogus_plugin_listing_normalizers(request, rf, member, mocker):
    normalizers = get_normalizers_data()
    mock_requests = mocker.patch("katalogus.client.httpx")
    mock_response = mocker.MagicMock()
    mock_requests.Client().get.return_value = mock_response
    mock_response.json.return_value = normalizers
    member = request.getfixturevalue(member)

    request = setup_request(rf.get("normalizers_list"), member.user)
    request.resolver_match = mocker.Mock(url_name="normalizers_list")
    response = NormalizerListView.as_view()(request, organization_code=member.organization.code)
    assert response.status_code == 200

    assertContains(response, "Normalizers")
    assertContains(
        response,
        '<li aria-current="page"><a href="/en/'
        + member.organization.code
        + '/kat-alogus/plugins/normalizers/grid/">Normalizers</a></li>',
        html=True,
    )
    assertContains(response, f"<strong>{len(normalizers)}</strong>Normalizers available", html=True)
    assertContains(response, '<span class="label-plugin-type normalizer">Normalizer</span>')
    assertNotContains(response, '<span class="label-plugin-type boefje">Boefje</span>')
    assertNotContains(response, "ssl-certificates")
    assertContains(response, "binaryedge")


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_katalogus_about_plugins(request, rf, member):
    member = request.getfixturevalue(member)

    response = AboutPluginsView.as_view()(
        setup_request(rf.get("about_plugins"), member.user), organization_code=member.organization.code
    )
    assert response.status_code == 200


def test_katalogus_plugin_listing_no_enable_disable_perm(rf, client_member, mocker):
    mock_requests = mocker.patch("katalogus.client.httpx")
    mock_response = mocker.MagicMock()
    mock_requests.Client().get.return_value = mock_response
    mock_response.json.return_value = get_plugins_data()

    request = rf.get("/en/test/kat-alogus/plugins/all/grid/")
    request.resolver_match = resolve(request.path)
    response = KATalogusView.as_view()(
        setup_request(request, client_member.user), organization_code=client_member.organization.code
    )
    assert response.status_code == 200
    assertContains(response, '<span class="label system-tag color-2">Enabled</span>')
    assertNotContains(response, '<button type="submit" class="button ghost">Enable</button>')
    assertNotContains(response, '<button type="submit" class="button ghost destructive">Disable</button>')


def test_katalogus_settings_one_organization(redteam_member, rf, mocker):
    # Mock katalogus calls: return right boefjes and settings
    mock_katalogus = mocker.patch("katalogus.client.KATalogusClient")
    boefjes_data = get_boefjes_data()
    mock_katalogus().get_boefjes.return_value = [parse_plugin(b) for b in boefjes_data if b["type"] == "boefje"]
    mock_katalogus().get_plugin_settings.return_value = {"BINARYEDGE_API": "test", "Second": "value"}

    request = setup_request(rf.get("katalogus_settings"), redteam_member.user)
    response = KATalogusSettingsView.as_view()(request, organization_code=redteam_member.organization.code)
    assert response.status_code == 200

    assertContains(response, "KAT-alogus settings")
    assertContains(response, "Plugin")
    assertContains(response, "Name")
    assertContains(response, "Value")
    assertContains(response, "BINARYEDGE_API")
    assertContains(response, "test")
    assertNotContains(response, "Clone settings")
    assertNotContains(response, "Organizations:")


def test_katalogus_settings_list_multiple_organization(redteam_member, organization_b, rf, mocker):
    # Mock katalogus calls: return right boefjes and settings
    mock_katalogus = mocker.patch("katalogus.client.KATalogusClient")
    boefjes_data = get_boefjes_data()
    mock_katalogus().get_boefjes.return_value = [parse_plugin(b) for b in boefjes_data if b["type"] == "boefje"]
    mock_katalogus().get_plugin_settings.return_value = {"BINARYEDGE_API": "test"}

    create_member(redteam_member.user, organization_b)

    request = setup_request(rf.get("katalogus_settings"), redteam_member.user)
    response = KATalogusSettingsView.as_view()(request, organization_code=redteam_member.organization.code)
    assert response.status_code == 200

    assertContains(response, "KAT-alogus settings")
    assertContains(response, "Plugin")
    assertContains(response, "Name")
    assertContains(response, "Value")
    assertContains(response, "BINARYEDGE_API")
    assertContains(response, "test")

    assertContains(response, "Clone settings")  # Now they appear
    assertContains(response, "Organizations:")  # Now they appear
    assertContains(response, organization_b.name)


def test_katalogus_confirm_clone_settings(redteam_member, organization_b, rf, mock_models_octopoes, mocker):
    mocker.patch("katalogus.client.KATalogusClient")

    create_member(redteam_member.user, organization_b)

    request = setup_request(rf.get("confirm_clone_settings"), redteam_member.user)
    response = ConfirmCloneSettingsView.as_view()(
        request, organization_code=redteam_member.organization.code, to_organization=organization_b.code
    )
    assert response.status_code == 200

    assertContains(response, "Clone settings")
    assertContains(response, "Be aware")
    assertContains(response, "Are you sure")
    assertContains(response, "Cancel")
    assertContains(response, "Clone")
    assertContains(response, redteam_member.organization.name)
    assertContains(response, organization_b.name)


def test_katalogus_clone_settings(redteam_member, organization_b, rf, mocker, mock_models_octopoes):
    mock_katalogus = mocker.patch("katalogus.client.KATalogusClient")

    member = create_member(redteam_member.user, organization_b)
    add_redteam_group_permissions(member)

    request = setup_request(rf.post("confirm_clone_settings"), redteam_member.user)
    response = ConfirmCloneSettingsView.as_view()(
        request, organization_code=redteam_member.organization.code, to_organization=organization_b.code
    )
    assert response.status_code == 302

    mock_katalogus().clone_all_configuration_to_organization.assert_called_once_with(
        redteam_member.organization.code, organization_b.code
    )


def test_katalogus_clone_settings_perm_to_organization(
    redteam_member, organization_b, rf, mocker, mock_models_octopoes
):
    mocker.patch("katalogus.client.KATalogusClient")

    create_member(redteam_member.user, organization_b)

    request = setup_request(rf.post("confirm_clone_settings"), redteam_member.user)
    with pytest.raises(KATalogusNotAllowedError):
        ConfirmCloneSettingsView.as_view()(
            request, organization_code=redteam_member.organization.code, to_organization=organization_b.code
        )


def test_katalogus_clone_settings_not_accessible_without_perms(
    client_member, organization_b, rf, mocker, mock_models_octopoes
):
    mocker.patch("katalogus.client.KATalogusClient")

    create_member(client_member.user, organization_b)

    request = setup_request(rf.post("confirm_clone_settings"), client_member.user)
    with pytest.raises(PermissionDenied):
        ConfirmCloneSettingsView.as_view()(
            request, organization_code=client_member.organization.code, to_organization=organization_b.code
        )


def test_katalogus_client_organization_not_exists(httpx_mock):
    httpx_mock.add_response(status_code=404)

    assert KATalogusClient("http://test").organization_exists("test") is False


def test_katalogus_client_organization_exists(mocker):
    mock_requests = mocker.patch("katalogus.client.httpx")
    mock_requests.Client().get().status_code = 200

    client = KATalogusClient("test")

    assert client.organization_exists("test") is True


def test_katalogus_client(httpx_mock):
    httpx_mock.add_response(json={"service": "test", "healthy": False, "version": None, "additional": 2, "results": []})

    client = KATalogusClient("http://test")

    assert isinstance(client.health(), ServiceHealth)
    assert client.health().service == "test"
    assert not client.health().healthy
    assert client.health().additional == 2
    assert client.health().results == []


def test_enable_disable_plugin_no_clearance(rf, redteam_member, mocker):
    redteam_member.trusted_clearance_level = -1
    redteam_member.acknowledged_clearance_level = -1
    redteam_member.save()

    plugin = get_boefjes_data()[0]
    mock_requests = mocker.patch("katalogus.client.httpx")
    mock_response = mocker.MagicMock()
    mock_requests.Client().get.return_value = mock_response
    mock_response.json.return_value = plugin

    request = setup_request(rf.post("plugin_enable_disable"), redteam_member.user)

    response = PluginEnableDisableView.as_view()(
        setup_request(request, redteam_member.user),
        organization_code=redteam_member.organization.code,
        plugin_type=plugin["type"],
        plugin_id=plugin["id"],
        plugin_state=False,
    )

    # redirects back to KAT-alogus
    assert response.status_code == 302

    assert (
        list(request._messages).pop().message
        == "To enable "
        + plugin["name"].title()
        + " you need at least a clearance level of L"
        + str(plugin["scan_level"])
        + ". "
        "Your clearance level is not set. Go to your profile page to see your clearance "
        "or contact the administrator to set a clearance level."
    )


def test_enable_disable_plugin_no_clearance_other_text(rf, redteam_member, mocker):
    redteam_member.trusted_clearance_level = 1
    redteam_member.acknowledged_clearance_level = 1
    redteam_member.save()

    plugin = get_boefjes_data()[0]
    mock_requests = mocker.patch("katalogus.client.httpx")
    mock_response = mocker.MagicMock()
    mock_requests.Client().get.return_value = mock_response
    mock_response.json.return_value = plugin

    request = setup_request(rf.post("plugin_enable_disable"), redteam_member.user)

    response = PluginEnableDisableView.as_view()(
        setup_request(request, redteam_member.user),
        organization_code=redteam_member.organization.code,
        plugin_type=plugin["type"],
        plugin_id=plugin["id"],
        plugin_state=False,
    )

    # redirects back to KAT-alogus
    assert response.status_code == 302

    assert (
        list(request._messages).pop().message
        == "To enable "
        + plugin["name"].title()
        + " you need at least a clearance level of L"
        + str(plugin["scan_level"])
        + ". Your clearance level is L"
        + str(redteam_member.acknowledged_clearance_level)
        + ". Contact your administrator to get a higher clearance level."
    )


def test_enable_disable_plugin_has_clearance(rf, redteam_member, mocker):
    plugin = get_boefjes_data()[0]
    mock_requests = mocker.patch("katalogus.client.httpx")
    mock_response = mocker.MagicMock()
    mock_requests.Client().get.return_value = mock_response
    mock_response.json.return_value = plugin

    request = setup_request(rf.post("plugin_enable_disable"), redteam_member.user)

    response = PluginEnableDisableView.as_view()(
        setup_request(request, redteam_member.user),
        organization_code=redteam_member.organization.code,
        plugin_type=plugin["type"],
        plugin_id=plugin["id"],
        plugin_state=False,
    )

    # redirects back to KAT-alogus
    assert response.status_code == 302

    assert list(request._messages).pop().message == "Boefje '" + plugin["name"] + "' enabled."


def test_enable_disable_normalizer(rf, redteam_member, mocker):
    plugin = get_normalizers_data()[0]
    mock_requests = mocker.patch("katalogus.client.httpx")
    mock_response = mocker.MagicMock()
    mock_requests.Client().get.return_value = mock_response
    mock_response.json.return_value = plugin

    request = setup_request(rf.post("plugin_enable_disable"), redteam_member.user)

    response = PluginEnableDisableView.as_view()(
        setup_request(request, redteam_member.user),
        organization_code=redteam_member.organization.code,
        plugin_type=plugin["type"],
        plugin_id=plugin["id"],
        plugin_state=False,
    )

    # redirects back to KAT-alogus
    assert response.status_code == 302

    assert list(request._messages).pop().message == "Normalizer '" + plugin["name"] + "' enabled."
