from crisis_room.models import AuditLog
from crisis_room.views import AuditLogView, OrganizationAuditLogView
from pytest_django.asserts import assertContains, assertNotContains

from tests.conftest import setup_request


def test_organization_audit_log(rf, client_member):
    AuditLog.record(
        user=client_member.user,
        organization=client_member.organization,
        action=AuditLog.Action.OBJECT_ADDED,
        object_type="Network",
        object_pk="Network|internet",
    )

    request = setup_request(rf.get("organization_crisis_room_audit_log"), client_member.user)
    response = OrganizationAuditLogView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "Activity log")
    assertContains(response, client_member.user.email)
    assertContains(response, "Added object")
    # The label is inferred from the stored PK at read time.
    assertContains(response, "internet")
    # The URL is constructed at read time from the stored PK.
    assertContains(response, "ooi_id=Network")


def test_general_audit_log_only_shows_accessible_organizations(rf, client_member, organization_b):
    AuditLog.record(
        user=client_member.user,
        organization=client_member.organization,
        action=AuditLog.Action.PLUGIN_ENABLED,
        object_label="Visible plugin",
    )
    AuditLog.record(
        user=client_member.user,
        organization=organization_b,
        action=AuditLog.Action.PLUGIN_ENABLED,
        object_label="Hidden plugin",
    )

    request = setup_request(rf.get("crisis_room_audit_log"), client_member.user)
    response = AuditLogView.as_view()(request)

    assert response.status_code == 200
    assertContains(response, "Visible plugin")
    assertNotContains(response, "Hidden plugin")


def test_audit_log_survives_a_hostile_page_parameter(rf, client_member):
    """?page= comes from the URL; a bad value must not 500."""
    AuditLog.record(
        user=client_member.user,
        organization=client_member.organization,
        action=AuditLog.Action.OBJECT_ADDED,
        object_pk="Network|internet",
    )

    for value in ("abc", "999", "0", "-1"):
        request = setup_request(rf.get("crisis_room_audit_log", {"page": value}), client_member.user)
        assert AuditLogView.as_view()(request).status_code == 200

        request = setup_request(rf.get("organization_crisis_room_audit_log", {"page": value}), client_member.user)
        assert (
            OrganizationAuditLogView.as_view()(request, organization_code=client_member.organization.code).status_code
            == 200
        )


def test_audit_log_pagination_controls(rf, client_member):
    for _ in range(51):
        AuditLog.record(
            user=client_member.user, organization=client_member.organization, action=AuditLog.Action.PLUGIN_ENABLED
        )

    request = setup_request(rf.get("crisis_room_audit_log"), client_member.user)
    response = AuditLogView.as_view()(request)

    assert response.status_code == 200
    assertContains(response, "?page=2")


def test_audit_log_entry_outlives_its_actor(client_member):
    entry = AuditLog.record(
        user=client_member.user,
        organization=client_member.organization,
        action=AuditLog.Action.OBJECT_ADDED,
        object_type="Network",
        object_pk="Network|internet",
    )
    user = client_member.user
    client_member.delete()  # OrganizationMember PROTECTs the account
    user.delete()

    entry.refresh_from_db()
    assert entry.actor is None
    assert entry.get_actor_label() == "client@openkat.nl"


def test_audit_log_unparseable_pk_renders_label_without_url(client_member):
    entry = AuditLog.record(
        user=client_member.user,
        organization=client_member.organization,
        action=AuditLog.Action.OBJECT_ADDED,
        object_pk="niet-een-reference",
    )

    assert entry.get_object_url() == ""
    assert entry.get_object_label() == "niet-een-reference"
