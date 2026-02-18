import pytest
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse
from httpx import HTTPError
from onboarding.view_helpers import DNS_REPORT_LEAST_CLEARANCE_LEVEL
from onboarding.views import (
    OnboardingAcknowledgeClearanceLevelView,
    OnboardingChooseReportTypeView,
    OnboardingClearanceLevelIntroductionView,
    OnboardingCreateReportRecipe,
    OnboardingIntroductionRegistrationView,
    OnboardingOrganizationSetupView,
    OnboardingOrganizationUpdateView,
    OnboardingReportView,
    OnboardingSetClearanceLevelView,
    OnboardingSetupScanOOIAddView,
    OnboardingSetupScanSelectPluginsView,
)
from pytest_django.asserts import assertContains, assertNotContains

from tests.conftest import setup_request


def test_onboarding_redirect(rf, superuser):
    """
    Make a request through the Django middleware to see if we get redirected to
    the onboarding flow when logging in as superuser.
    """
    c = Client()
    login = c.force_login(superuser)
    print(login)
    response = c.get("/")
    print(response)
    assert response.status_code == 302
    assert response.headers["Location"] == reverse("step_1_introduction_registration")


def test_step_1_onboarding_introduction(superuser_member, rf):
    response = OnboardingIntroductionRegistrationView.as_view()(
        setup_request(rf.get("step_1_introduction_registration"), superuser_member.user),
        organization_code=superuser_member.organization.code,
    )

    assert response.status_code == 200
    assertContains(response, "Welcome to OpenKAT")
    assertContains(response, "Let's get started")


@pytest.mark.parametrize("member", ["admin_member", "redteam_member", "client_member"])
def test_step_1_onboarding_introduction_forbidden(request, member, rf):
    member = request.getfixturevalue(member)

    with pytest.raises(PermissionDenied):
        OnboardingIntroductionRegistrationView.as_view()(
            setup_request(rf.get("step_1_introduction_registration"), member.user),
            organization_code=member.organization.code,
        )


def test_step_2a_onboarding_create_organization(rf, superuser_member, mock_models_katalogus):
    request = setup_request(
        rf.post("step_2a_organization_setup", {"name": "Test Organization", "code": "test"}), superuser_member.user
    )
    mock_models_katalogus().organization_exists.return_value = False

    response = OnboardingOrganizationSetupView.as_view()(request)
    assert response.status_code == 200
    assertContains(response, "Test Organization")


@pytest.mark.parametrize("member", ["admin_member", "redteam_member", "client_member"])
def test_step_2a_onboarding_create_organization_forbidden(request, rf, member, mock_models_katalogus):
    member = request.getfixturevalue(member)

    request = setup_request(
        rf.post("step_2a_organization_setup", {"name": "Test Organization", "code": "test"}), member.user
    )
    mock_models_katalogus().organization_exists.return_value = False

    with pytest.raises(PermissionDenied):
        OnboardingOrganizationSetupView.as_view()(request)


def test_step_2a_onboarding_create_organization_already_exist_katalogus(
    rf, superuser, mock_katalogus_client, mock_models_octopoes, mocker
):
    mocker.patch("katalogus.client.KATalogusClient")
    mocker.patch("rocky.signals.OctopoesAPIConnector")
    mocker.patch("crisis_room.management.commands.dashboards.scheduler_client")
    mocker.patch("crisis_room.management.commands.dashboards.get_bytes_client")
    request = setup_request(
        rf.post("step_2a_organization_setup", {"name": "Test Organization", "code": "test"}), superuser
    )

    mock_katalogus_client().organization_exists.return_value = True
    mock_katalogus_client().create_organization.side_effect = HTTPError("")

    response = OnboardingOrganizationSetupView.as_view()(request)
    assert response.status_code == 302
    assert response.headers["Location"] == reverse("step_3_indemnification_setup", kwargs={"organization_code": "test"})


def test_step_2b_onboarding_organization_update(rf, superuser_member, admin_member, redteam_member, client_member):
    response_superuser = OnboardingOrganizationUpdateView.as_view()(
        setup_request(rf.get("step_2b_organization_setup"), superuser_member.user),
        organization_code=superuser_member.organization.code,
    )
    response_admin = OnboardingOrganizationUpdateView.as_view()(
        setup_request(rf.get("step_2b_organization_setup"), admin_member.user),
        organization_code=admin_member.organization.code,
    )

    # Only superusers and admins can update/edt/change organizations
    assert response_superuser.status_code == 200
    assert response_admin.status_code == 200

    with pytest.raises(PermissionDenied):
        OnboardingOrganizationUpdateView.as_view()(
            setup_request(rf.get("step_2b_organization_setup"), redteam_member.user),
            organization_code=redteam_member.organization.code,
        )

    with pytest.raises(PermissionDenied):
        OnboardingOrganizationUpdateView.as_view()(
            setup_request(rf.get("step_2b_organization_setup"), client_member.user),
            organization_code=client_member.organization.code,
        )


def test_step_4_onboarding_acknowledge_clearance_level(rf, redteam_member, mock_organization_view_octopoes, url):
    response = OnboardingAcknowledgeClearanceLevelView.as_view()(
        setup_request(
            rf.get("step_4_trusted_acknowledge_clearance_level", {"ooi": url.primary_key}), redteam_member.user
        ),
        organization_code=redteam_member.organization.code,
    )

    assert response.status_code == 200
    assertContains(response, "Onboarding")
    assertContains(response, "User clearance level")
    assertContains(response, "Trusted clearance level")
    assertContains(response, "Accepted clearance level")
    assertContains(response, "What is my clearance level?")
    assertContains(response, "Continue")
    assertContains(response, "Skip onboarding")
    assertContains(
        response,
        "Your administrator has <strong>trusted</strong> you with a clearance level of <strong>L"
        + str(redteam_member.trusted_clearance_level)
        + "</strong>.",
    )
    (
        "You have also <strong>acknowledged</strong> to use this clearance level of <strong>L"
        + str(redteam_member.acknowledged_clearance_level)
        + "</strong>."
    )

    redteam_member.trusted_clearance_level = 2
    redteam_member.acknowledged_clearance_level = -1
    redteam_member.save()

    response_accept = OnboardingAcknowledgeClearanceLevelView.as_view()(
        setup_request(
            rf.get("step_4_trusted_acknowledge_clearance_level", {"ooi": url.primary_key}), redteam_member.user
        ),
        organization_code=redteam_member.organization.code,
    )

    assertContains(
        response_accept,
        "Your administrator has trusted you with a clearance level of <strong>L"
        + str(redteam_member.trusted_clearance_level)
        + "</strong>.",
    )
    assertContains(response_accept, "You must first accept this clearance level to continue.")


@pytest.mark.parametrize("clearance_level", [-1, 0])
def test_step_4_onboarding_acknowledge_clearance_level_no_clearance(
    rf, redteam_member, clearance_level, mock_organization_view_octopoes, url
):
    response = OnboardingAcknowledgeClearanceLevelView.as_view()(
        setup_request(
            rf.get("step_4_trusted_acknowledge_clearance_level", {"ooi": url.primary_key}), redteam_member.user
        ),
        organization_code=redteam_member.organization.code,
    )

    assert response.status_code == 200
    redteam_member.trusted_clearance_level = clearance_level
    redteam_member.acknowledged_clearance_level = clearance_level
    redteam_member.save()

    response = OnboardingAcknowledgeClearanceLevelView.as_view()(
        setup_request(
            rf.get("step_4_trusted_acknowledge_clearance_level", {"ooi": url.primary_key}), redteam_member.user
        ),
        organization_code=redteam_member.organization.code,
    )
    assertContains(response, "Unfortunately you cannot continue the onboarding.")
    assertContains(
        response,
        "Your administrator has trusted you with a clearance level of <strong>L" + str(clearance_level) + "</strong>.",
    )
    assertContains(
        response,
        "You need at least a clearance level of <strong>L"
        + str(DNS_REPORT_LEAST_CLEARANCE_LEVEL)
        + "</strong> to scan <strong>"
        + url.primary_key
        + "</strong>",
    )
    assertContains(response, "Contact your administrator to receive a higher clearance.")

    assertContains(response, "Skip onboarding")


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_step_5_onboarding_setup_scan_detail(request, member, rf):
    member = request.getfixturevalue(member)

    response = OnboardingSetupScanOOIAddView.as_view()(
        setup_request(rf.get("step_setup_scan_ooi_add", {"report_type": "dns-report"}), member.user),
        ooi_type="URL",
        organization_code=member.organization.code,
    )

    assert response.status_code == 200

    assertContains(response, "Onboarding")
    assertContains(response, "Plugins")
    assertContains(response, "Add an object")
    assertContains(response, "Related objects")
    assertContains(response, "Skip onboarding")


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_step_5_onboarding_setup_scan_detail_create_ooi(
    request, member, rf, mock_organization_view_octopoes, url, mock_bytes_client
):
    member = request.getfixturevalue(member)

    response = OnboardingSetupScanOOIAddView.as_view()(
        setup_request(rf.post("step_setup_scan_ooi_add", {"url": url.raw}), member.user),
        ooi_type="URL",
        organization_code=member.organization.code,
    )

    assert response.status_code == 302


def test_step_6_onboarding_set_clearance_level(
    rf, superuser_member, admin_member, redteam_member, client_member, mock_organization_view_octopoes, url
):
    response_superuser = OnboardingSetClearanceLevelView.as_view()(
        setup_request(rf.get("step_6_set_clearance_level", {"ooi": url.primary_key}), superuser_member.user),
        organization_code=superuser_member.organization.code,
    )
    response_redteam = OnboardingSetClearanceLevelView.as_view()(
        setup_request(rf.get("step_6_set_clearance_level", {"ooi": url.primary_key}), redteam_member.user),
        organization_code=redteam_member.organization.code,
    )

    assert response_redteam.status_code == 200
    assert response_superuser.status_code == 200

    assertContains(response_redteam, "Onboarding")
    assertContains(response_redteam, "Set object clearance level")
    assertContains(response_redteam, "Skip onboarding")
    assertContains(response_redteam, "Set clearance level")

    with pytest.raises(PermissionDenied):
        OnboardingSetClearanceLevelView.as_view()(
            setup_request(rf.get("step_6_set_clearance_level", {"ooi": url.primary_key}), admin_member.user),
            organization_code=admin_member.organization.code,
        )
    with pytest.raises(PermissionDenied):
        OnboardingSetClearanceLevelView.as_view()(
            setup_request(rf.get("step_6_set_clearance_level", {"ooi": url.primary_key}), client_member.user),
            organization_code=client_member.organization.code,
        )


def test_step_7_onboarding_clearance_level_introduction(rf, redteam_member, mock_organization_view_octopoes, url):
    response = OnboardingClearanceLevelIntroductionView.as_view()(
        setup_request(rf.get("step_clearance_level_introduction", {"ooi": url.primary_key}), redteam_member.user),
        organization_code=redteam_member.organization.code,
    )

    assert response.status_code == 200
    assertContains(response, "Onboarding")
    assertContains(response, "Plugin introduction")
    assertContains(response, "Fierce")
    assertContains(response, "DNS-Zone")
    assertContains(response, "Skip onboarding")
    assertContains(response, "Continue")

    assertNotContains(response, '<div class="action-buttons">', html=True)


@pytest.mark.parametrize("member", ["superuser_member", "redteam_member"])
def test_step_8_onboarding_select_plugins(request, member, rf, mocker, mock_organization_view_octopoes, url):
    mocker.patch("account.mixins.OrganizationView.get_katalogus")
    member = request.getfixturevalue(member)
    request = setup_request(rf.get("step_setup_scan_select_plugins", {"ooi": url.primary_key}), member.user)

    response = OnboardingSetupScanSelectPluginsView.as_view()(request, organization_code=member.organization.code)

    assert response.status_code == 200

    assertContains(response, "Enabling plugins and start scanning")
    assertContains(response, "Boefjes")
    assertContains(response, "Normalizers")
    assertContains(response, "Bits")
    assertContains(response, "Skip onboarding")
    assertContains(response, "Enable and continue")


@pytest.mark.parametrize("member", ["admin_member", "client_member"])
def test_step_8_onboarding_select_plugins_perms(request, member, rf, url):
    member = request.getfixturevalue(member)

    request = setup_request(rf.get("step_setup_scan_select_plugins", {"ooi": url.primary_key}), member.user)

    with pytest.raises(PermissionDenied):
        OnboardingSetupScanSelectPluginsView.as_view()(request, organization_code=member.organization.code)


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_step_9_onboarding_choose_report_type(request, member, rf):
    member = request.getfixturevalue(member)
    response = OnboardingChooseReportTypeView.as_view()(
        setup_request(rf.get("step_choose_report_type"), member.user), organization_code=member.organization.code
    )

    assert response.status_code == 200
    assertContains(response, "Onboarding")
    assertContains(response, "Skip onboarding")
    assertContains(response, "Generate DNS Report")


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_step_9a_onboarding_ooi_detail_scan(
    request, mocker, member, mock_bytes_client, rf, mock_organization_view_octopoes, url
):
    member = request.getfixturevalue(member)

    mocker.patch("account.mixins.OrganizationView.get_katalogus")
    mocker.patch("crisis_room.management.commands.dashboards.scheduler_client")
    mock_organization_view_octopoes().get.return_value = url
    mock_bytes_client().upload_raw.return_value = "raw_id"

    response = OnboardingCreateReportRecipe.as_view()(
        setup_request(rf.get("step_9a_setup_scan_ooi_detail", {"ooi": url.primary_key}), member.user),
        organization_code=member.organization.code,
    )

    assert response.status_code == 200

    assertContains(response, "Onboarding")
    assertContains(response, "Generate a report")
    assertContains(response, "Skip onboarding")
    assertContains(response, "Generate DNS Report")


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_step_9a_onboarding_ooi_detail_scan_create_report_schedule(
    request, mocker, member, mock_scheduler, mock_bytes_client, rf, mock_organization_view_octopoes, url
):
    member = request.getfixturevalue(member)

    mocker.patch("account.mixins.OrganizationView.get_katalogus")
    mocker.patch("crisis_room.management.commands.dashboards.scheduler_client")
    mock_organization_view_octopoes().get.return_value = url
    mock_bytes_client().upload_raw.return_value = "raw_id"

    request_url = (
        reverse("step_9a_setup_scan_ooi_detail", kwargs={"organization_code": member.organization.code})
        + f"?report_type=dns-report&ooi={url.primary_key}"
    )

    response = OnboardingCreateReportRecipe.as_view()(
        setup_request(rf.post(request_url), member.user), organization_code=member.organization.code
    )

    assert response.status_code == 302
    assert "recipe_id" in response.url


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_step_10_onboarding_scanning_boefjes(
    request, member, rf, mock_organization_view_octopoes, url, mocker, mock_bytes_client
):
    member = request.getfixturevalue(member)

    mocker.patch("account.mixins.OrganizationView.get_katalogus")
    mock_organization_view_octopoes().get.return_value = url
    mock_bytes_client().upload_raw.return_value = "raw_id"

    request_url = (
        reverse("step_10_report", kwargs={"organization_code": member.organization.code})
        + f"?report_type=dns-report&ooi={url.primary_key}"
    )

    response = OnboardingReportView.as_view()(
        setup_request(rf.post(request_url), member.user), organization_code=member.organization.code
    )

    assert response.status_code == 302
