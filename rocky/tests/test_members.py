import pytest
from django.core.exceptions import PermissionDenied
from django.http import Http404
from pytest_django.asserts import assertContains, assertNotContains

from rocky.views.organization_member_add import OrganizationMemberAddAccountTypeView, OrganizationMemberAddView
from rocky.views.organization_member_edit import OrganizationMemberEditView
from tests.conftest import setup_request


def test_admin_can_edit_itself(rf, admin_member):
    """
    This will test if an admin member can edit itself.
    """

    request = setup_request(rf.get("organization_member_edit"), admin_member.user)
    response = OrganizationMemberEditView.as_view()(
        request, organization_code=admin_member.organization.code, pk=admin_member.id
    )
    assert response.status_code == 200
    assertContains(response, "Edit member")


def test_superuser_can_edit_itself(rf, superuser_member):
    """
    This will test if a superuser can edit itself.
    """

    request = setup_request(rf.get("organization_member_edit"), superuser_member.user)
    response = OrganizationMemberEditView.as_view()(
        request, organization_code=superuser_member.organization.code, pk=superuser_member.id
    )
    assert response.status_code == 200
    assertContains(response, "Edit member")


def test_client_can_edit_itself(rf, client_member):
    """
    This will test if a client member can edit itself. Only admins and superusers have edit rights.
    """

    request = setup_request(rf.get("organization_member_edit"), client_member.user)
    with pytest.raises(PermissionDenied):
        OrganizationMemberEditView.as_view()(
            request, organization_code=client_member.organization.code, pk=client_member.id
        )


def test_redteam_can_edit_itself(rf, redteam_member):
    """
    This will test if a redteam member can edit itself. Only admins and supersuers have edit rights.
    """

    request = setup_request(rf.get("organization_member_edit"), redteam_member.user)
    with pytest.raises(PermissionDenied):
        OrganizationMemberEditView.as_view()(
            request, organization_code=redteam_member.organization.code, pk=redteam_member.id
        )


def test_admin_can_edit_superuser(rf, admin_member, superuser_member):
    """
    This will test if admin can edit superuser at the member edit view.
    """

    request = setup_request(rf.get("organization_member_edit"), admin_member.user)
    with pytest.raises(PermissionDenied):
        OrganizationMemberEditView.as_view()(
            request, organization_code=superuser_member.organization.code, pk=superuser_member.id
        )


def test_client_can_edit_superuser(rf, client_member, superuser_member):
    """
    This will test if client can edit superuser at the member edit view.
    """

    request = setup_request(rf.get("organization_member_edit"), client_member.user)
    with pytest.raises(PermissionDenied):
        OrganizationMemberEditView.as_view()(
            request, organization_code=superuser_member.organization.code, pk=superuser_member.id
        )


def test_redteamer_can_edit_superuser(rf, redteam_member, superuser_member, organization):
    """
    This will test if redteamer can edit superuser at the member edit view.
    """

    request = setup_request(rf.get("organization_member_edit"), redteam_member.user)
    with pytest.raises(PermissionDenied):
        OrganizationMemberEditView.as_view()(request, organization_code=organization.code, pk=superuser_member.id)


def test_edit_superusers_from_different_organizations(rf, superuser_member, superuser_member_b):
    """
    This will test if a superuser from one organization can edit
    a superuser from another organization at the member edit view.
    """

    request = setup_request(rf.get("organization_member_edit"), superuser_member.user)
    # from OrganizationView
    OrganizationMemberEditView.as_view()(
        request, organization_code=superuser_member_b.organization.code, pk=superuser_member_b.id
    )


def test_edit_admins_from_different_organizations(rf, admin_member, admin_member_b):
    """
    This will check that an admin from one organization cannot edit
    an admin from another organization at the member edit view.
    """

    request = setup_request(rf.get("organization_member_edit"), admin_member.user)
    # from OrganizationView
    with pytest.raises(Http404):
        OrganizationMemberEditView.as_view()(
            request, organization_code=admin_member_b.organization.code, pk=admin_member_b.id
        )


def test_admin_edits_client_different_orgs(rf, admin_member, client_member_b):
    request = setup_request(
        rf.post("organization_member_edit", {"status": "blocked", "trusted_clearance_level": 4}), admin_member.user
    )
    with pytest.raises(Http404):
        OrganizationMemberEditView.as_view()(
            request, organization_code=client_member_b.organization.code, pk=client_member_b.id
        )


def test_admin_edits_redteamer(rf, admin_member, redteam_member, log_output):
    request = setup_request(
        rf.post("organization_member_edit", {"status": "active", "trusted_clearance_level": 4}), admin_member.user
    )
    OrganizationMemberEditView.as_view()(
        request, organization_code=redteam_member.organization.code, pk=redteam_member.id
    )

    redteam_member.refresh_from_db()
    assert redteam_member.status == "active"
    assert redteam_member.trusted_clearance_level == 4

    organization_member_updated_log = log_output.entries[-1]
    assert organization_member_updated_log["event"] == "%s %s updated"
    assert organization_member_updated_log["object"] == "redteamer@openkat.nl"
    assert organization_member_updated_log["object_type"] == "OrganizationMember"


def test_admin_edits_redteamer_to_block(rf, admin_member, redteam_member):
    request = setup_request(
        rf.post("organization_member_edit", {"blocked": True, "trusted_clearance_level": 4}), admin_member.user
    )
    OrganizationMemberEditView.as_view()(
        request, organization_code=redteam_member.organization.code, pk=redteam_member.id
    )

    redteam_member.refresh_from_db()
    assert redteam_member.blocked is True


def test_account_type_view_existence(rf, admin_member):
    response = OrganizationMemberAddAccountTypeView.as_view()(
        setup_request(rf.get("organization_member_add_account_type"), admin_member.user),
        organization_code=admin_member.organization.code,
    )

    assert response.status_code == 200


def test_check_add_redteamer_form(rf, admin_member):
    response = OrganizationMemberAddView.as_view()(
        setup_request(rf.get("organization_member_add"), admin_member.user),
        organization_code=admin_member.organization.code,
        account_type="redteam",
    )

    assert response.status_code == 200
    assertContains(response, "Redteam account setup")

    # Check first and last radio input of trusted clearance level form input
    assertContains(
        response,
        '<input type="radio" name="trusted_clearance_level" value="-1" radio_paws="True" '
        'id="id_trusted_clearance_level_0" required="True" checked="True" checked="True">',
        html=True,
    )
    assertContains(
        response,
        '<input type="radio" name="trusted_clearance_level" value="4" radio_paws="True" '
        'id="id_trusted_clearance_level_5" required="True">',
        html=True,
    )


@pytest.mark.parametrize("account_type", ["admin", "client"])
def test_check_add_admin_client_form(rf, admin_member, account_type):
    response = OrganizationMemberAddView.as_view()(
        setup_request(rf.get("organization_member_add"), admin_member.user),
        organization_code=admin_member.organization.code,
        account_type=account_type,
    )

    assert response.status_code == 200
    assertContains(response, account_type.capitalize() + " account setup")

    # Check first and last radio input of trusted clearance level form input
    assertNotContains(
        response,
        '<input type="radio" name="trusted_clearance_level" value="-1" id="id_trusted_clearance_level_0" checked="">',
        html=True,
    )
    assertNotContains(
        response,
        '<input type="radio" name="trusted_clearance_level" value="4" id="id_trusted_clearance_level_5">',
        html=True,
    )
