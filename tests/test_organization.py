import pytest
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains

from objects.models import Network, XTDBOrganization
from openkat.models import DENY_ORGANIZATION_CODES, Indemnification, Organization, OrganizationMember
from openkat.views.indemnification_add import IndemnificationAddView
from openkat.views.organization_add import OrganizationAddView
from openkat.views.organization_edit import OrganizationEditView
from openkat.views.organization_list import OrganizationListView
from openkat.views.organization_member_list import OrganizationMemberListView
from openkat.views.organization_settings import OrganizationSettingsView
from tests.conftest import setup_request

AMOUNT_OF_TEST_ORGANIZATIONS = 50


@pytest.fixture
def bulk_organizations(active_member, blocked_member):
    organizations = []
    members = []
    indemnifications = []

    for i in range(1, AMOUNT_OF_TEST_ORGANIZATIONS):
        org = Organization(name=f"Test Organization {i}", code=f"test{i}", tags=f"test-tag{i}")
        organizations.append(org)

    orgs = Organization.objects.bulk_create(organizations)

    for organization in orgs:
        for member in [active_member, blocked_member]:
            members.append(
                OrganizationMember(
                    user=member.user,
                    organization=organization,
                    blocked=False,
                    trusted_clearance_level=4,
                    acknowledged_clearance_level=4,
                )
            )
            indemnifications.append(Indemnification(user=member.user, organization=organization))

    OrganizationMember.objects.bulk_create(members)
    Indemnification.objects.bulk_create(indemnifications)

    return orgs


def test_organization_list_non_superuser(rf, client_member):
    client_member.user.user_permissions.add(Permission.objects.get(codename="view_organization"))

    request = setup_request(rf.get("organization_list"), client_member.user)
    response = OrganizationListView.as_view()(request)

    assertContains(response, "Organizations")
    assertNotContains(response, "Add new organization")
    assertContains(response, client_member.organization.name)


def test_edit_organization(rf, superuser_member):
    request = setup_request(rf.get("organization_edit"), superuser_member.user)
    response = OrganizationEditView.as_view()(request, organization_code=superuser_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "Name")
    assertContains(response, "Code")
    assertContains(response, superuser_member.organization.code)
    assertContains(response, superuser_member.organization.name)
    assertContains(response, "Save organization")


def test_add_organization_page(rf, superuser_member):
    request = setup_request(rf.get("organization_add"), superuser_member.user)
    response = OrganizationAddView.as_view()(request, organization_code=superuser_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "Name")
    assertContains(response, "Code")
    assertContains(response, superuser_member.organization.code)
    assertContains(response, superuser_member.organization.name)
    assertContains(response, "Organization setup")


@pytest.mark.skip("This test is too flaky for now.")
def test_add_organization_submit_success(rf, superuser_member, log_output):
    request = setup_request(rf.post("organization_add", {"name": "neworg", "code": "norg"}), superuser_member.user)
    response = OrganizationAddView.as_view()(request, organization_code=superuser_member.organization.code)
    assert response.status_code == 302

    messages = list(request._messages)
    assert "Organization added successfully" in messages[0].message

    logs = [e for e in log_output.entries if e["event"] != "Connected to RabbitMQ"]
    group_client_log, group_admin_log = logs[0], logs[2]
    superuser_log_created, superuser_log_updated = logs[3], logs[4]
    static_device_log, static_token_log = logs[5], logs[6]

    superuser_organization_log = logs[7]

    dashboard_log, dashboard_log_data_created = logs[8], logs[9]

    dashboard_log_data_updated = logs[15]

    superuser_indemnification = logs[16]
    superuser_organization_member = logs[17]

    this_organization = logs[18]
    this_organization_dashboard = logs[19]
    this_organization_dashboard_data_created = logs[20]

    this_organization_dashboard_data_updated = logs[26]
    this_organization_organization_member_created = logs[27]
    this_organization_organization_member_updated = logs[28]

    # groups are created
    assert group_client_log["event"] == "%s %s created"
    assert group_admin_log["event"] == "%s %s created"

    # superuser created and updated
    assert superuser_log_created["event"] == "%s %s created"
    assert superuser_log_updated["event"] == "%s %s updated"

    # 2AF created
    assert static_device_log["event"] == "%s %s created"
    assert static_token_log["event"] == "%s %s created"

    # superuser org created
    assert superuser_organization_log["event"] == "%s %s created"

    # dashboard and dashboard data created and updated
    assert dashboard_log["event"] == "%s %s created"
    assert dashboard_log_data_created["event"] == "%s %s created"
    assert dashboard_log_data_updated["event"] == "%s %s updated"

    # create indemnification for superuser
    assert superuser_indemnification["event"] == "%s %s created"

    # create superuser member
    assert superuser_organization_member["event"] == "%s %s created"
    assert superuser_organization_member["object"] == "superuser@openkat.nl"
    assert superuser_organization_member["object_type"] == "OrganizationMember"

    # Organization created for this test
    assert this_organization["event"] == "%s %s created"
    assert this_organization["object"] == "neworg"
    assert this_organization["object_type"] == "Organization"

    # dashboard and dashboard data created and updated for this test (when org is created)
    assert this_organization_dashboard["event"] == "%s %s created"
    assert this_organization_dashboard_data_created["event"] == "%s %s created"
    assert this_organization_dashboard_data_updated["event"] == "%s %s updated"

    # member created and updated for this org
    assert this_organization_organization_member_created["event"] == "%s %s created"
    assert this_organization_organization_member_updated["event"] == "%s %s updated"


def test_organization_list(rf, superuser_member, bulk_organizations, django_assert_max_num_queries):
    """Verify that this view does not query the database for each organization."""

    with django_assert_max_num_queries(
        AMOUNT_OF_TEST_ORGANIZATIONS, info="Too many queries for organization list view"
    ):
        request = setup_request(rf.get("organization_list"), superuser_member.user)
        response = OrganizationListView.as_view()(request)

        assertContains(response, "Organizations")
        assertContains(response, "Add new organization")
        assertContains(response, superuser_member.organization.name)

        for org in bulk_organizations:
            assertContains(response, org.name)


def test_organization_member_list(rf, admin_member):
    request = setup_request(rf.get("organization_member_list"), admin_member.user)
    response = OrganizationMemberListView.as_view()(request, organization_code=admin_member.organization.code)

    assertContains(response, "Organization")
    assertContains(response, admin_member.organization.name)
    assertContains(response, "Members")
    assertContains(response, "Add member(s)")
    assertNotContains(response, "Name")
    assertNotContains(response, admin_member.user.full_name)
    assertContains(response, "E-mail")
    assertContains(response, admin_member.user.email)
    assertContains(response, "Role")
    assertContains(response, "Admin")

    # We should not be showing information about the User to just any admin in an organization
    assertNotContains(response, "Added")
    assertNotContains(response, admin_member.user.date_joined.strftime("%m/%d/%Y"))

    assertContains(response, "Assigned clearance level")
    assertContains(response, admin_member.trusted_clearance_level)
    assertContains(response, "Accepted clearance level")
    assertContains(response, admin_member.acknowledged_clearance_level)
    assertContains(response, "Edit")
    assertContains(response, admin_member.id)
    assertContains(response, "Blocked")


def test_organization_filtered_member_list(rf, superuser_member, blocked_member):
    # Test with only filter option blocked status "blocked"
    request = setup_request(rf.get("organization_member_list", {"blocked": "blocked"}), superuser_member.user)
    response = OrganizationMemberListView.as_view()(request, organization_code=superuser_member.organization.code)

    assertNotContains(response, blocked_member.user.full_name)


def test_organization_does_not_exist(client, client_member):
    client.force_login(client_member.user)
    response = client.get(reverse("organization_settings", kwargs={"organization_code": "nonexistent"}))

    assert response.status_code == 404


def test_organization_no_member(client, clientuser, organization):
    client.force_login(clientuser)
    response = client.get(reverse("organization_settings", kwargs={"organization_code": organization.code}))

    assert response.status_code == 404


def test_organization_active_member(rf, admin_member):
    # Default is already active
    request = setup_request(rf.get("organization_settings"), admin_member.user)
    response = OrganizationSettingsView.as_view()(request, organization_code=admin_member.organization.code)

    assert response.status_code == 200


def test_organization_blocked_member(rf, admin_member):
    admin_member.blocked = True
    admin_member.save()
    request = setup_request(rf.get("organization_settings"), admin_member.user)
    with pytest.raises(PermissionDenied):
        OrganizationSettingsView.as_view()(request, organization_code=admin_member.organization.code)


def test_edit_organization_permissions(rf, client_member):
    request_client = setup_request(rf.get("organization_edit"), client_member.user)

    with pytest.raises(PermissionDenied):
        OrganizationEditView.as_view()(
            request_client, organization_code=client_member.organization.code, pk=client_member.organization.id
        )


def test_edit_organization_indemnification(rf, client_member):
    request_client = setup_request(rf.get("indemnification_add"), client_member.user)

    with pytest.raises(PermissionDenied):
        IndemnificationAddView.as_view()(
            request_client, organization_code=client_member.organization.code, pk=client_member.organization.id
        )


def test_admin_rights_edits_organization(rf, admin_member):
    request = setup_request(rf.get("organization_edit"), admin_member.user)
    response = OrganizationEditView.as_view()(
        request, organization_code=admin_member.organization.code, pk=admin_member.organization.id
    )

    assert response.status_code == 200


def test_admin_edits_organization(rf, admin_member):
    request = setup_request(
        rf.post("organization_edit", {"name": "This organization name has been edited", "tags": "tag1,tag2"}),
        admin_member.user,
    )
    response = OrganizationEditView.as_view()(
        request, organization_code=admin_member.organization.code, pk=admin_member.organization.id
    )

    assert response.status_code == 302
    assert response.url == f"/en/{admin_member.organization.code}/settings"
    resulted_request = setup_request(rf.get(response.url), admin_member.user)
    resulted_response = OrganizationSettingsView.as_view()(
        resulted_request, organization_code=admin_member.organization.code
    )
    assert resulted_response.status_code == 200

    assertContains(resulted_response, "Tags")
    assertContains(resulted_response, "tags-color-1-light plain")  # default color
    assertContains(resulted_response, "tag1")
    assertContains(resulted_response, "tag2")


def test_organization_code_validator_from_view(rf, superuser_member):
    request = setup_request(
        rf.post("organization_add", {"name": "DENIED LIST CHECK", "code": DENY_ORGANIZATION_CODES[0]}),
        superuser_member.user,
    )

    response = OrganizationAddView.as_view()(request)

    assert response.status_code == 200
    assertContains(
        response, "This organization code is reserved by OpenKAT and cannot be used. Choose another organization code."
    )


@pytest.mark.django_db(databases=["xtdb", "default"])
def test_organization_code_validator_from_model():
    with pytest.raises(ValidationError):
        Organization.objects.create(name="Test", code=DENY_ORGANIZATION_CODES[0])

    new_org = Organization.objects.create(name="Test", code="test_123")
    assert new_org.code == "test_123"

    new_org.code = DENY_ORGANIZATION_CODES[0]
    with pytest.raises(ValidationError):
        new_org.save()


def test_organization_settings_perms(rf, superuser_member, admin_member, client_member):
    response_superuser = OrganizationSettingsView.as_view()(
        setup_request(rf.get("organization_settings"), superuser_member.user),
        organization_code=superuser_member.organization.code,
    )

    response_admin = OrganizationSettingsView.as_view()(
        setup_request(rf.get("organization_settings"), admin_member.user),
        organization_code=admin_member.organization.code,
    )

    assert response_superuser.status_code == 200
    assert response_admin.status_code == 200
    assertContains(response_superuser, "Edit")
    assertContains(response_admin, "Edit")
    assertContains(response_superuser, "Add indemnification")
    assertContains(response_admin, "Add indemnification")

    with pytest.raises(PermissionDenied):
        OrganizationSettingsView.as_view()(
            setup_request(rf.get("organization_settings"), client_member.user),
            organization_code=client_member.organization.code,
        )


def test_organization_member_list_perms(rf, superuser_member, admin_member, client_member):
    response_superuser = OrganizationMemberListView.as_view()(
        setup_request(rf.get("organization_member_list"), superuser_member.user),
        organization_code=superuser_member.organization.code,
    )

    response_admin = OrganizationMemberListView.as_view()(
        setup_request(rf.get("organization_member_list"), admin_member.user),
        organization_code=admin_member.organization.code,
    )

    assert response_superuser.status_code == 200
    assert response_admin.status_code == 200

    with pytest.raises(PermissionDenied):
        OrganizationMemberListView.as_view()(
            setup_request(rf.get("organization_member_list"), client_member.user),
            organization_code=client_member.organization.code,
        )


def test_organization_list_perms(rf, superuser_member, admin_member, client_member):
    response_superuser = OrganizationListView.as_view()(
        setup_request(rf.get("organization_list"), superuser_member.user),
        organization_code=superuser_member.organization.code,
    )

    response_admin = OrganizationListView.as_view()(
        setup_request(rf.get("organization_list"), admin_member.user), organization_code=admin_member.organization.code
    )

    response_client = OrganizationListView.as_view()(
        setup_request(rf.get("organization_list"), client_member.user),
        organization_code=client_member.organization.code,
    )

    assertContains(response_superuser, "Add new organization")

    # Non-superuser can not add organization
    assertNotContains(response_admin, "Add new organization")
    assertNotContains(response_client, "Add new organization")


@pytest.mark.django_db(databases=["xtdb", "default"])
@pytest.mark.parametrize("member", ["superuser_member", "admin_member"])
def test_organization_edit_perms(request, member, rf):
    member = request.getfixturevalue(member)

    response = OrganizationEditView.as_view()(
        setup_request(rf.get("organization_edit"), member.user),
        organization_code=member.organization.code,
        pk=member.organization.id,
    )

    assert response.status_code == 200


@pytest.mark.django_db(databases=["xtdb", "default"])
@pytest.mark.parametrize("member", ["superuser_member", "admin_member"])
def test_organization_edit_view(request, member, rf):
    member = request.getfixturevalue(member)

    response = OrganizationSettingsView.as_view()(
        setup_request(rf.get("organization_settings"), member.user), organization_code=member.organization.code
    )

    assert response.status_code == 200
    assertContains(response, "Edit")
    assertContains(response, "icon ti-edit")


@pytest.mark.django_db(databases=["xtdb", "default"])
def test_organization_edit_perms_on_settings_view(request, client_member, rf):
    with pytest.raises(PermissionDenied):
        OrganizationSettingsView.as_view()(
            setup_request(rf.get("organization_settings"), client_member.user),
            organization_code=client_member.organization.code,
        )


def test_organization_tags(organization):
    assert list(organization.tags.all()) == []

    organization.tags = ["testtag1", "testtag2"]
    organization.save()
    assert list(organization.tags.all()) == ["testtag1", "testtag2"]

    organization = Organization.objects.create(name="testtags", code="testtags", tags=["testtag3", "testtag4"])
    assert list(organization.tags.all()) == ["testtag3", "testtag4"]

    organization.tags = []
    organization.save()
    assert list(organization.tags.all()) == []


def test_organization_delete(xtdb):
    organization = Organization.objects.create(name="deletetest", code="deletetest", tags=["testtag4"])
    net = Network.objects.create(name="test")
    net.organizations.add(XTDBOrganization.objects.get(pk=organization.pk))
    net.save()
    net.refresh_from_db()
    assert net.organizations.first() == XTDBOrganization.objects.get(pk=organization.pk)

    organization.delete(using="default")
