from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains
from tools.models import Indemnification

from rocky.views.ooi_add_subnet import SubnetAddView
from tests.conftest import setup_request


def test_subnet_add_review_step(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """Step 1 submit renders the review step with the computed range."""
    mock_organization_view_octopoes().list_objects.return_value.items = []

    request = setup_request(
        rf.post("ooi_add_subnet", {"step": "1", "cidr": "192.168.5.0/24", "network": "internet", "name": "office-lan"}),
        redteam_member.user,
    )
    response = SubnetAddView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "192.168.5.0")
    assertContains(response, "192.168.5.255")
    assertContains(response, "256 addresses")
    # Canonical input: no normalization notice
    assertNotContains(response, "was interpreted as the subnet")
    # Nothing saved while reviewing
    mock_organization_view_octopoes().save_many_declarations.assert_not_called()


def test_subnet_add_review_step_normalizes_host_bits(
    rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client
):
    """An interface address with host bits set is normalized, and the review step says so."""
    mock_organization_view_octopoes().list_objects.return_value.items = []

    request = setup_request(
        rf.post("ooi_add_subnet", {"step": "1", "cidr": "192.168.5.77/24", "network": "internet", "name": ""}),
        redteam_member.user,
    )
    response = SubnetAddView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "was interpreted as the subnet")
    assertContains(response, "192.168.5.0/24")
    # The review shows the canonical start IP
    assertContains(response, "Start IP")


def test_subnet_add_confirm_saves_batch_and_clearance(
    rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client
):
    """Step 2 submit saves network, start IP and NetBlock in one batch and declares the clearance level."""
    mock_organization_view_octopoes().list_objects.return_value.items = []

    request = setup_request(
        rf.post(
            "ooi_add_subnet",
            {
                "step": "2",
                "cidr": "192.168.5.0/24",
                "network": "internet",
                "name": "office-lan",
                "clearance_level": "2",
            },
        ),
        redteam_member.user,
    )
    response = SubnetAddView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert "IPV4NetBlock%7Cinternet%7Cinternet%7C192.168.5.0%7C24" in response.url
    mock_bytes_client().add_manual_proof.assert_called_once()
    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    assert [declaration.ooi.__class__.__name__ for declaration in declarations] == [
        "Network",
        "IPAddressV4",
        "IPV4NetBlock",
    ]

    # Clearance level declared on the NetBlock
    mock_organization_view_octopoes().save_scan_profile.assert_called_once()


def test_subnet_add_confirm_without_clearance(rf, client_member, mock_organization_view_octopoes, mock_bytes_client):
    """A member without the clearance permission can add the subnet, but no scan profile is declared."""
    mock_organization_view_octopoes().list_objects.return_value.items = []

    request = setup_request(
        rf.post("ooi_add_subnet", {"step": "2", "cidr": "192.168.5.0/24", "network": "internet", "name": ""}),
        client_member.user,
    )
    response = SubnetAddView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 302
    mock_organization_view_octopoes().save_scan_profile.assert_not_called()


def test_subnet_add_blocks_post_without_user_indemnification(
    rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client
):
    """A user who did not accept indemnification themselves is redirected and nothing is saved."""
    Indemnification.objects.filter(user=redteam_member.user, organization=redteam_member.organization).delete()

    request = setup_request(
        rf.post("ooi_add_subnet", {"step": "2", "cidr": "192.168.5.0/24", "network": "internet"}), redteam_member.user
    )
    response = SubnetAddView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert (
        reverse("indemnification_add", kwargs={"organization_code": redteam_member.organization.code}) in response.url
    )
    mock_organization_view_octopoes().save_many_declarations.assert_not_called()


def test_subnet_add_get_without_user_indemnification_shows_disabled_form(
    rf, redteam_member, mock_organization_view_octopoes
):
    mock_organization_view_octopoes().list_objects.return_value.items = []
    Indemnification.objects.filter(user=redteam_member.user, organization=redteam_member.organization).delete()

    request = setup_request(rf.get("ooi_add_subnet"), redteam_member.user)
    response = SubnetAddView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "indemnification")
    assertContains(response, "disabled")


def test_subnet_add_clearance_capped_at_member_maximum(
    rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client
):
    """The review step only offers clearance levels up to the member's own maximum."""
    mock_organization_view_octopoes().list_objects.return_value.items = []
    redteam_member.acknowledged_clearance_level = 1
    redteam_member.save()

    request = setup_request(
        rf.post("ooi_add_subnet", {"step": "1", "cidr": "192.168.5.0/24", "network": "internet", "name": ""}),
        redteam_member.user,
    )
    response = SubnetAddView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "L1")
    assertNotContains(response, "L2")


def test_subnet_add_invalid_cidr(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    mock_organization_view_octopoes().list_objects.return_value.items = []

    request = setup_request(
        rf.post("ooi_add_subnet", {"step": "1", "cidr": "not-a-cidr", "network": "internet", "name": ""}),
        redteam_member.user,
    )
    response = SubnetAddView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "Enter a valid CIDR")
    mock_organization_view_octopoes().save_many_declarations.assert_not_called()
