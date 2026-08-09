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
        object_label="internet",
        object_url="/objects/internet/",
    )

    request = setup_request(rf.get("organization_crisis_room_audit_log"), client_member.user)
    response = OrganizationAuditLogView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "Activity log")
    assertContains(response, client_member.user.email)
    assertContains(response, "Added object")
    assertContains(response, 'href="/objects/internet/"')


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
