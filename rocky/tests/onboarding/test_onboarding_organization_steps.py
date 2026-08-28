import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from onboarding.view_helpers import DNS_REPORT_LEAST_CLEARANCE_LEVEL
from onboarding.views import (
    OnboardingAcknowledgeClearanceLevelView,
    OnboardingChooseReportInfoView,
    OnboardingChooseReportTypeView,
    OnboardingClearanceLevelIntroductionView,
    OnboardingIntroductionView,
    OnboardingReportView,
    OnboardingSetClearanceLevelView,
    OnboardingSetupScanOOIAddView,
    OnboardingSetupScanOOIDetailView,
    OnboardingSetupScanOOIInfoView,
    OnboardingSetupScanSelectPluginsView,
)
from pytest_django.asserts import assertContains, assertNotContains

from tests.conftest import setup_request


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_onboarding_introduction(request, member, rf):
    member = request.getfixturevalue(member)
    response = OnboardingIntroductionView.as_view()(
        setup_request(rf.get("step_introduction"), member.user), organization_code=member.organization.code
    )

    assert response.status_code == 200
    assertContains(response, "Welcome to OpenKAT")
    assertContains(response, "Skip onboarding")
    assertContains(response, "Let's get started")


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_onboarding_choose_report_info(request, member, rf):
    member = request.getfixturevalue(member)
    response = OnboardingChooseReportInfoView.as_view()(
        setup_request(rf.get("step_choose_report_info"), member.user), organization_code=member.organization.code
    )

    assert response.status_code == 200

    assertContains(response, "KAT introduction")
    assertContains(response, "Reports")
    assertContains(response, "Data")
    assertContains(response, "Skip onboarding")
    assertContains(response, "Let's choose a report")


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_onboarding_choose_report_type(request, member, rf):
    member = request.getfixturevalue(member)
    response = OnboardingChooseReportTypeView.as_view()(
        setup_request(rf.get("step_choose_report_type"), member.user), organization_code=member.organization.code
    )

    assert response.status_code == 200
    assertContains(response, "KAT introduction")
    assertContains(response, "Choose a report - Type")
    assertContains(response, "Skip onboarding")
    assertContains(response, "DNS Report")
    assertContains(response, "Pentest")
    assertContains(response, "Mail Report")
    assertContains(response, "DigiD")


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_onboarding_setup_scan(request, member, rf):
    member = request.getfixturevalue(member)
    response = OnboardingSetupScanOOIInfoView.as_view()(
        setup_request(rf.get("step_setup_scan_ooi_info"), member.user), organization_code=member.organization.code
    )

    assert response.status_code == 200

    assertContains(response, "KAT introduction")
    assertContains(response, "Setup scan")
    assertContains(response, "Let OpenKAT know what object to scan")
    assertContains(response, "Understanding objects")
    assertContains(response, "Skip onboarding")
    assertContains(response, "Add URL")


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_onboarding_setup_scan_detail(request, member, rf):
    member = request.getfixturevalue(member)

    response = OnboardingSetupScanOOIAddView.as_view()(
        setup_request(rf.get("step_setup_scan_ooi_add", {"report_type": "dns-report"}), member.user),
        ooi_type="URL",
        organization_code=member.organization.code,
    )

    assert response.status_code == 200

    assertContains(response, "KAT introduction")
    assertContains(response, "Setup scan")
    assertContains(response, "Creating an object")
    assertContains(response, "Dependencies")
    assertContains(response, "Create object")
    assertContains(response, "Skip onboarding")


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_onboarding_setup_scan_detail_create_ooi(
    request, member, rf, mock_organization_view_octopoes, url, mock_bytes_client
):
    member = request.getfixturevalue(member)

    response = OnboardingSetupScanOOIAddView.as_view()(
        setup_request(rf.post("step_setup_scan_ooi_add", {"url": url.raw}), member.user),
        ooi_type="URL",
        organization_code=member.organization.code,
    )

    assert response.status_code == 302


def test_onboarding_clearance_level_introduction(rf, redteam_member, mock_organization_view_octopoes, url):
    response = OnboardingClearanceLevelIntroductionView.as_view()(
        setup_request(rf.get("step_clearance_level_introduction", {"ooi": url.primary_key}), redteam_member.user),
        organization_code=redteam_member.organization.code,
    )

    assert response.status_code == 200
    assertContains(response, "OpenKAT introduction")
    assertContains(response, "OOI clearance for " + url.human_readable)
    assertContains(response, "Introduction")
    assertContains(response, "How to know required clearance level")
    assertContains(response, "Fierce")
    assertContains(response, "DNS-Zone")
    assertContains(response, "Skip onboarding")
    assertContains(response, "Continue")

    assertNotContains(response, '<div class="action-buttons">', html=True)


def test_onboarding_acknowledge_clearance_level(rf, redteam_member, mock_organization_view_octopoes, url):
    response = OnboardingAcknowledgeClearanceLevelView.as_view()(
        setup_request(rf.get("step_acknowledge_clearance_level", {"ooi": url.primary_key}), redteam_member.user),
        organization_code=redteam_member.organization.code,
    )

    assert response.status_code == 200
    assertContains(response, "OpenKAT introduction")
    assertContains(response, "Setup scan - OOI clearance for " + url.human_readable)
    assertContains(response, "Trusted clearance level")
    assertContains(response, "Acknowledge clearance level")
    assertContains(response, "What is my clearance level?")
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
    assertContains(response, "Set clearance level")

    redteam_member.trusted_clearance_level = 2
    redteam_member.acknowledged_clearance_level = -1
    redteam_member.save()

    response_accept = OnboardingAcknowledgeClearanceLevelView.as_view()(
        setup_request(rf.get("step_acknowledge_clearance_level", {"ooi": url.primary_key}), redteam_member.user),
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
def test_onboarding_acknowledge_clearance_level_no_clearance(
    rf, redteam_member, clearance_level, mock_organization_view_octopoes, url
):
    response = OnboardingAcknowledgeClearanceLevelView.as_view()(
        setup_request(rf.get("step_acknowledge_clearance_level", {"ooi": url.primary_key}), redteam_member.user),
        organization_code=redteam_member.organization.code,
    )

    assert response.status_code == 200
    redteam_member.trusted_clearance_level = clearance_level
    redteam_member.acknowledged_clearance_level = clearance_level
    redteam_member.save()

    response = OnboardingAcknowledgeClearanceLevelView.as_view()(
        setup_request(rf.get("step_acknowledge_clearance_level", {"ooi": url.primary_key}), redteam_member.user),
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


def test_onboarding_set_clearance_level(
    rf, superuser_member, admin_member, redteam_member, client_member, mock_organization_view_octopoes, url
):
    response_superuser = OnboardingSetClearanceLevelView.as_view()(
        setup_request(rf.get("step_set_clearance_level", {"ooi": url.primary_key}), superuser_member.user),
        organization_code=superuser_member.organization.code,
    )
    response_redteam = OnboardingSetClearanceLevelView.as_view()(
        setup_request(rf.get("step_set_clearance_level", {"ooi": url.primary_key}), redteam_member.user),
        organization_code=redteam_member.organization.code,
    )

    assert response_redteam.status_code == 200
    assert response_superuser.status_code == 200

    assertContains(response_redteam, "OpenKAT introduction")
    assertContains(response_redteam, "Setup scan - Set clearance level for " + str(url.human_readable))
    assertContains(response_redteam, "Set clearance level")
    assertContains(response_redteam, "Skip onboarding")

    with pytest.raises(PermissionDenied):
        OnboardingSetClearanceLevelView.as_view()(
            setup_request(rf.get("step_set_clearance_level", {"ooi": url.primary_key}), admin_member.user),
            organization_code=admin_member.organization.code,
        )
    with pytest.raises(PermissionDenied):
        OnboardingSetClearanceLevelView.as_view()(
            setup_request(rf.get("step_set_clearance_level", {"ooi": url.primary_key}), client_member.user),
            organization_code=client_member.organization.code,
        )


@pytest.mark.parametrize("member", ["superuser_member", "redteam_member"])
def test_onboarding_select_plugins(request, member, rf, mocker, mock_organization_view_octopoes, url):
    mocker.patch("account.mixins.OrganizationView.get_katalogus")
    member = request.getfixturevalue(member)
    request = setup_request(rf.get("step_setup_scan_select_plugins", {"ooi": url.primary_key}), member.user)

    response = OnboardingSetupScanSelectPluginsView.as_view()(request, organization_code=member.organization.code)

    assert response.status_code == 200

    assertContains(response, "Setup scan - Enable plugins")
    assertContains(response, "Plugins introduction")
    assertContains(response, "Boefjes")
    assertContains(response, "Normalizers")
    assertContains(response, "Bits")
    assertContains(response, "Required and suggested plugins")
    assertContains(response, "Skip onboarding")
    assertContains(response, "Enable and start scan")


@pytest.mark.parametrize("member", ["admin_member", "client_member"])
def test_onboarding_select_plugins_perms(request, member, rf, url):
    member = request.getfixturevalue(member)

    request = setup_request(rf.get("step_setup_scan_select_plugins", {"ooi": url.primary_key}), member.user)

    with pytest.raises(PermissionDenied):
        OnboardingSetupScanSelectPluginsView.as_view()(request, organization_code=member.organization.code)


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_onboarding_ooi_detail_scan(
    request, mocker, member, mock_bytes_client, rf, mock_organization_view_octopoes, url
):
    member = request.getfixturevalue(member)

    mocker.patch("account.mixins.OrganizationView.get_katalogus")
    mocker.patch("crisis_room.management.commands.dashboards.scheduler_client")
    mock_organization_view_octopoes().get.return_value = url
    mock_bytes_client().upload_raw.return_value = "raw_id"

    response = OnboardingSetupScanOOIDetailView.as_view()(
        setup_request(rf.get("step_setup_scan_ooi_detail", {"ooi": url.primary_key}), member.user),
        organization_code=member.organization.code,
    )

    assert response.status_code == 200

    assertContains(response, "KAT introduction")
    assertContains(response, "Setup scan")
    assertContains(response, "Creating an object")
    assertContains(response, "Network")
    assertContains(response, "Skip onboarding")
    assertContains(response, "Start scanning")


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_onboarding_ooi_detail_scan_create_report_schedule(
    request, mocker, member, mock_scheduler, mock_bytes_client, rf, mock_organization_view_octopoes, url
):
    member = request.getfixturevalue(member)

    mocker.patch("account.mixins.OrganizationView.get_katalogus")
    mocker.patch("crisis_room.management.commands.dashboards.scheduler_client")
    mock_organization_view_octopoes().get.return_value = url
    mock_bytes_client().upload_raw.return_value = "raw_id"

    request_url = (
        reverse("step_setup_scan_ooi_detail", kwargs={"organization_code": member.organization.code})
        + f"?report_type=dns-report&ooi={url.primary_key}"
    )

    response = OnboardingSetupScanOOIDetailView.as_view()(
        setup_request(rf.post(request_url), member.user), organization_code=member.organization.code
    )

    assert response.status_code == 302
    assert "recipe_id" in response.url


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member", "client_member"])
def test_onboarding_scanning_boefjes(
    request, member, rf, mock_organization_view_octopoes, url, mocker, mock_bytes_client
):
    member = request.getfixturevalue(member)

    mocker.patch("account.mixins.OrganizationView.get_katalogus")
    mock_organization_view_octopoes().get.return_value = url
    mock_bytes_client().upload_raw.return_value = "raw_id"

    request_url = (
        reverse("step_report", kwargs={"organization_code": member.organization.code})
        + f"?report_type=dns-report&ooi={url.primary_key}"
    )

    response = OnboardingReportView.as_view()(
        setup_request(rf.post(request_url), member.user), organization_code=member.organization.code
    )

    assert response.status_code == 302
