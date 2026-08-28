from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from tools.models import Organization, OrganizationTag


def test_organizationtag_cssclass():
    tag = OrganizationTag(color="blue-dark", border_type="dashed")

    assert tag.css_class == "tags-blue-dark dashed"


def test_user_organization_cache(superuser_member, django_assert_num_queries):
    with django_assert_num_queries(1):
        assert len(superuser_member.user.organizations) == 1
        assert len(superuser_member.user.organizations) == 1


def test_organizationmember_no_permissions(active_member, django_assert_num_queries):
    with django_assert_num_queries(3):
        assert not active_member.has_perm("tools.view_organization")
        assert not active_member.has_perm("tools.can_scan_organization")
        assert not active_member.has_perm("tools.can_enable_disable_boefje")


def test_organizationmember_permissions(active_member, django_assert_num_queries):
    content_type = ContentType.objects.get_for_model(Organization)
    view_organization = Permission.objects.get(codename="view_organization", content_type=content_type)
    can_scan_organization = Permission.objects.get(codename="can_scan_organization", content_type=content_type)
    can_enable_disable_boefje = Permission.objects.get(codename="can_enable_disable_boefje", content_type=content_type)

    group1 = Group.objects.create(name="group1")
    group2 = Group.objects.create(name="group2")

    active_member.user.user_permissions.add(view_organization)
    group1.permissions.add(can_scan_organization)
    group2.permissions.add(can_enable_disable_boefje)

    active_member.user.groups.add(group1)
    active_member.groups.add(group2)

    with django_assert_num_queries(3):
        assert active_member.has_perm("tools.view_organization")
        assert active_member.has_perm("tools.can_scan_organization")
        assert active_member.has_perm("tools.can_enable_disable_boefje")


def test_organizationmember_permissions_superuser(superuser_member, django_assert_num_queries):
    with django_assert_num_queries(1):
        assert superuser_member.has_perm("tools.view_organization")
        assert superuser_member.has_perm("tools.can_scan_organization")
        assert superuser_member.has_perm("tools.can_enable_disable_boefje")


def test_user_two_organization(client_user_two_organizations, organization, organization_b):
    assert client_user_two_organizations.organizations == [organization, organization_b]
    assert client_user_two_organizations.organizations_including_blocked == [organization, organization_b]


def test_user_one_organization(client_member, organization_b):
    assert client_member.user.organizations == [client_member.organization]


def test_user_organization_blocked(blocked_member, organization_b):
    assert blocked_member.user.organizations == []


def test_superuser_organizations(superuser, organization, organization_b):
    assert superuser.organizations == [organization_b, organization]


def test_can_access_all_organizations(client_member, organization_b):
    content_type = ContentType.objects.get_for_model(Organization)
    can_access_all_organizations = Permission.objects.get(
        codename="can_access_all_organizations", content_type=content_type
    )

    client_member.user.user_permissions.add(can_access_all_organizations)

    assert client_member.user.organizations == [organization_b, client_member.organization]


def test_max_clearance_level(client_member):
    client_member.user.clearance_level = -1
    client_member.trusted_clearance_level = -1
    client_member.acknowledged_clearance_level = -1

    assert client_member.max_clearance_level == -1

    client_member.user.clearance_level = 4
    client_member.trusted_clearance_level = -1
    client_member.acknowledged_clearance_level = -1

    assert client_member.max_clearance_level == 4

    client_member.user.clearance_level = -1
    client_member.trusted_clearance_level = 4
    client_member.acknowledged_clearance_level = 4

    assert client_member.max_clearance_level == 4

    client_member.user.clearance_level = 4
    client_member.trusted_clearance_level = 2
    client_member.acknowledged_clearance_level = 2

    assert client_member.max_clearance_level == 2

    client_member.user.clearance_level = 2
    client_member.trusted_clearance_level = 4
    client_member.acknowledged_clearance_level = 4

    assert client_member.max_clearance_level == 4


def test_max_clearance_level_not_acknowledged(client_member):
    client_member.user.clearance_level = 2
    client_member.trusted_clearance_level = 1
    client_member.acknowledged_clearance_level = -1

    assert client_member.max_clearance_level == -1

    client_member.user.clearance_level = 2
    client_member.trusted_clearance_level = -1
    client_member.acknowledged_clearance_level = 1

    assert client_member.max_clearance_level == -1

    client_member.user.clearance_level = -1
    client_member.trusted_clearance_level = -1
    client_member.acknowledged_clearance_level = 1

    assert client_member.max_clearance_level == -1

    client_member.user.clearance_level = -1
    client_member.trusted_clearance_level = 2
    client_member.acknowledged_clearance_level = -1

    assert client_member.max_clearance_level == -1

    client_member.user.clearance_level = -1
    client_member.trusted_clearance_level = 2
    client_member.acknowledged_clearance_level = 1

    assert client_member.max_clearance_level == 1
