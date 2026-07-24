import pytest
from django.contrib.messages import get_messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.test import Client
from django.urls import reverse
from django_otp import DEVICE_ID_SESSION_KEY
from pytest_django.asserts import assertContains, assertNotContains

from rocky.views.organization_member_add import OrganizationMemberAddAccountTypeView, OrganizationMemberAddView
from rocky.views.organization_member_edit import OrganizationMemberEditView
from rocky.views.organization_member_superuser import SUPERUSER_ACCESS_GRANTED_EVENT_CODE, GrantSuperuserAccessView
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


def test_superuser_sees_grant_superuser_action(rf, superuser_member, admin_member):
    request = setup_request(rf.get("organization_member_edit"), superuser_member.user)
    response = OrganizationMemberEditView.as_view()(
        request, organization_code=admin_member.organization.code, pk=admin_member.id
    )

    assertContains(response, "Global account access")
    assertContains(
        response,
        reverse(
            "organization_member_grant_superuser",
            kwargs={"organization_code": admin_member.organization.code, "pk": admin_member.id},
        ),
    )


def test_admin_does_not_see_grant_superuser_action(rf, admin_member, redteam_member):
    request = setup_request(rf.get("organization_member_edit"), admin_member.user)
    response = OrganizationMemberEditView.as_view()(
        request, organization_code=redteam_member.organization.code, pk=redteam_member.id
    )

    assertNotContains(response, "Global account access")
    assertNotContains(response, "Grant superuser access")


def test_superuser_can_view_grant_superuser_confirmation(rf, superuser_member, admin_member):
    request = setup_request(rf.get("organization_member_grant_superuser"), superuser_member.user)
    response = GrantSuperuserAccessView.as_view()(
        request, organization_code=admin_member.organization.code, pk=admin_member.id
    )

    assertContains(response, "Grant superuser access")
    assertContains(response, admin_member.user.email)
    assertContains(response, "unrestricted access to every organization")
    assertContains(response, "clear both Superuser status and Staff status")
    assertContains(response, reverse("admin:account_katuser_change", args=[admin_member.user.id]))
    assertContains(response, "csrfmiddlewaretoken")


def test_superuser_can_grant_superuser_access(
    rf, superuser_member, admin_member, log_output, django_capture_on_commit_callbacks
):
    log_output.entries.clear()
    request = setup_request(rf.post("organization_member_grant_superuser"), superuser_member.user)
    with django_capture_on_commit_callbacks(execute=True):
        response = GrantSuperuserAccessView.as_view()(
            request, organization_code=admin_member.organization.code, pk=admin_member.id
        )

    assert response.status_code == 302
    assert response.url == reverse(
        "organization_member_list", kwargs={"organization_code": admin_member.organization.code}
    )

    admin_member.user.refresh_from_db()
    assert admin_member.user.is_superuser is True
    assert admin_member.user.is_staff is True

    audit_log = log_output.entries[-1]
    assert audit_log["event"] == "Superuser access granted"
    assert audit_log["event_code"] == SUPERUSER_ACCESS_GRANTED_EVENT_CODE
    assert audit_log["actor_id"] == superuser_member.user.id
    assert audit_log["target_id"] == admin_member.user.id
    assert audit_log["previous_is_superuser"] is False
    assert audit_log["previous_is_staff"] is False
    assert audit_log["is_superuser"] is True
    assert audit_log["is_staff"] is True
    assert audit_log["changed_at"]


def test_grant_superuser_access_does_not_log_a_rolled_back_change(
    rf, superuser_member, admin_member, log_output, django_capture_on_commit_callbacks
):
    log_output.entries.clear()
    request = setup_request(rf.post("organization_member_grant_superuser"), superuser_member.user)

    with django_capture_on_commit_callbacks(execute=True), pytest.raises(RuntimeError), transaction.atomic():
        GrantSuperuserAccessView.as_view()(
            request, organization_code=admin_member.organization.code, pk=admin_member.id
        )
        raise RuntimeError

    admin_member.user.refresh_from_db()
    assert admin_member.user.is_superuser is False
    assert admin_member.user.is_staff is False
    assert not any(entry.get("event") == "Superuser access granted" for entry in log_output.entries)


@pytest.mark.parametrize("actor_fixture", ["admin_member", "redteam_member", "client_member"])
def test_non_superusers_cannot_grant_superuser_access(rf, request, actor_fixture, redteam_member):
    actor = request.getfixturevalue(actor_fixture)
    view_request = setup_request(rf.post("organization_member_grant_superuser"), actor.user)

    with pytest.raises(PermissionDenied):
        GrantSuperuserAccessView.as_view()(
            view_request, organization_code=redteam_member.organization.code, pk=redteam_member.id
        )

    redteam_member.user.refresh_from_db()
    assert redteam_member.user.is_superuser is False
    assert redteam_member.user.is_staff is False


def test_non_superuser_cannot_determine_if_grant_target_exists(rf, admin_member, redteam_member):
    existing_target = setup_request(rf.post("organization_member_grant_superuser"), admin_member.user)
    missing_target = setup_request(rf.post("organization_member_grant_superuser"), admin_member.user)

    with pytest.raises(PermissionDenied):
        GrantSuperuserAccessView.as_view()(
            existing_target, organization_code=redteam_member.organization.code, pk=redteam_member.id
        )

    with pytest.raises(PermissionDenied):
        GrantSuperuserAccessView.as_view()(
            missing_target, organization_code=redteam_member.organization.code, pk=redteam_member.id + 100_000
        )


def test_grant_superuser_access_is_idempotent(rf, superuser_member, superuser_member_b, log_output):
    superuser_member_b.user.is_staff = True
    superuser_member_b.user.save(update_fields=["is_staff"])
    log_output.entries.clear()
    request = setup_request(rf.post("organization_member_grant_superuser"), superuser_member.user)
    response = GrantSuperuserAccessView.as_view()(
        request, organization_code=superuser_member_b.organization.code, pk=superuser_member_b.id
    )

    assert response.status_code == 302
    superuser_member_b.user.refresh_from_db()
    assert superuser_member_b.user.is_superuser is True
    assert superuser_member_b.user.is_staff is True
    assert [str(message) for message in get_messages(request)] == [
        f"{superuser_member_b.user.email} already has superuser access."
    ]
    assert not any(entry.get("event") == "Superuser access granted" for entry in log_output.entries)


def test_inactive_user_cannot_be_granted_superuser_access(rf, superuser_member, admin_member):
    admin_member.user.is_active = False
    admin_member.user.save(update_fields=["is_active"])
    request = setup_request(rf.post("organization_member_grant_superuser"), superuser_member.user)

    response = GrantSuperuserAccessView.as_view()(
        request, organization_code=admin_member.organization.code, pk=admin_member.id
    )

    assert response.status_code == 302
    admin_member.user.refresh_from_db()
    assert admin_member.user.is_superuser is False
    assert admin_member.user.is_staff is False
    assert [str(message) for message in get_messages(request)] == [
        f"{admin_member.user.email} is inactive and cannot be granted superuser access."
    ]


def test_grant_superuser_access_requires_csrf(superuser_member, client_member):
    superuser_member.onboarded = True
    superuser_member.save(update_fields=["onboarded"])
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(superuser_member.user)
    session = csrf_client.session
    session[DEVICE_ID_SESSION_KEY] = superuser_member.user.staticdevice_set.get().persistent_id
    session.save()
    url = reverse(
        "organization_member_grant_superuser",
        kwargs={"organization_code": client_member.organization.code, "pk": client_member.id},
    )

    response = csrf_client.get(url)
    assert response.status_code == 200

    response = csrf_client.post(url)
    assert response.status_code == 403
    client_member.user.refresh_from_db()
    assert client_member.user.is_superuser is False
    assert client_member.user.is_staff is False

    response = csrf_client.post(url, {"csrfmiddlewaretoken": csrf_client.cookies["csrftoken"].value})
    assert response.status_code == 302
    client_member.user.refresh_from_db()
    assert client_member.user.is_superuser is True
    assert client_member.user.is_staff is True


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
