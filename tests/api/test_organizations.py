import pytest
from django.contrib.auth.models import Permission

from openkat.management.commands.create_authtoken import create_auth_token
from openkat.models import Indemnification, Organization
from tests.conftest import JSONAPIClient, create_user


@pytest.fixture
def organizations(xtdb):
    return [
        Organization.objects.create(**org)
        for org in [
            {"name": "Test Organization 1", "code": "test1", "tags": ["tag1", "tag2"]},
            {"name": "Test Organization 2", "code": "test2"},
        ]
    ]


@pytest.fixture
def organization_for_indemnification(xtdb):
    return Organization.objects.create(name="Test Org Indem", code="test_indem")


@pytest.fixture
def user_with_indemnification(django_user_model, organization_for_indemnification):
    user = create_user(django_user_model, "test@example.com", "Test123!!", "Test User", "device1")
    Indemnification.objects.create(user=user, organization=organization_for_indemnification)
    return user


@pytest.fixture
def admin_client(adminuser):
    _, token = create_auth_token(adminuser.email, "test_admin_key")
    client = JSONAPIClient(raise_request_exception=False)
    client.credentials(HTTP_AUTHORIZATION="Token " + token)
    return client


def test_list_organizations(drf_client, organizations):
    response = drf_client.get("/api/v1/organization/")
    assert response.status_code == 200, f"Response: {response.content}"

    data = response.json()

    if isinstance(data, dict) and "results" in data:
        orgs_list = data["results"]
    elif isinstance(data, list):
        orgs_list = data
    else:
        raise AssertionError(f"Unexpected response format: {data}")

    org_map = {org["code"]: org for org in orgs_list}

    assert "test1" in org_map
    assert org_map["test1"]["name"] == "Test Organization 1"
    assert org_map["test1"]["code"] == "test1"
    assert sorted(org_map["test1"]["tags"]) == ["tag1", "tag2"]

    assert "test2" in org_map
    assert org_map["test2"]["name"] == "Test Organization 2"
    assert org_map["test2"]["code"] == "test2"


def test_create_organization(drf_client, xtdb):
    initial_count = Organization.objects.count()
    data = {"name": "Test Org 3", "code": "test3", "tags": ["tag2", "tag3"]}

    response = drf_client.post("/api/v1/organization/", json=data)
    assert response.status_code == 201

    result = response.json()
    assert result["name"] == "Test Org 3"
    assert result["code"] == "test3"
    assert sorted(result["tags"]) == ["tag2", "tag3"]

    assert Organization.objects.count() == initial_count + 1
    org = Organization.objects.get(pk=result["id"])
    assert org.name == "Test Org 3"
    assert org.code == "test3"
    assert sorted(str(tag) for tag in org.tags.all()) == ["tag2", "tag3"]


def test_create_organization_no_permission(admin_client, admin_member, xtdb):
    data = {"name": "Test Org 3", "code": "test3", "tags": ["tag2", "tag3"]}

    response = admin_client.post("/api/v1/organization/", json=data)
    assert response.status_code == 403


def test_retrieve_organization(admin_client, admin_member, organizations):
    org = organizations[0]
    response = admin_client.get(f"/api/v1/organization/{org.pk}/")
    assert response.status_code == 200

    result = response.json()
    assert result["id"] == org.pk
    assert result["name"] == "Test Organization 1"
    assert result["code"] == "test1"
    assert sorted(result["tags"]) == ["tag1", "tag2"]


def test_update_organization(drf_client, organizations):
    org = organizations[0]
    data = {"name": "Changed Organization", "code": "test4", "tags": ["tag3", "tag4"]}

    response = drf_client.patch(f"/api/v1/organization/{org.pk}/", json=data)
    assert response.status_code == 200

    result = response.json()
    assert result["name"] == "Changed Organization"
    assert result["code"] == "test1"
    assert sorted(result["tags"]) == ["tag3", "tag4"]

    org.refresh_from_db()
    assert org.name == "Changed Organization"
    assert org.code == "test1"
    assert sorted(str(tag) for tag in org.tags.all()) == ["tag3", "tag4"]


def test_destroy_organization(drf_client, organizations):
    initial_count = Organization.objects.count()

    response = drf_client.delete(f"/api/v1/organization/{organizations[0].pk}/")
    assert response.status_code == 204

    assert Organization.objects.count() == initial_count - 1
    assert not Organization.objects.filter(pk=organizations[0].pk).exists()


def test_destroy_organization_no_permission(admin_client, admin_member, organizations):
    org = organizations[0]
    response = admin_client.delete(f"/api/v1/organization/{org.pk}/")
    assert response.status_code == 403


def test_get_indemnification(drf_client, organization_for_indemnification, user_with_indemnification):
    response = drf_client.get(f"/api/v1/organization/{organization_for_indemnification.pk}/indemnification/")
    assert response.status_code == 200

    result = response.json()
    assert result["indemnification"] is True
    assert result["user"] == user_with_indemnification.id


def test_get_indemnification_does_not_exist(drf_client, organization_for_indemnification):
    org = Organization.objects.create(name="Test Org No Indem", code="test_no_indem")

    response = drf_client.get(f"/api/v1/organization/{org.pk}/indemnification/")
    assert response.status_code == 200

    result = response.json()
    assert result["indemnification"] is False
    assert result["user"] is None


def test_set_indemnification(admin_client, admin_user, xtdb):
    org = Organization.objects.create(name="Test Org for Set Indem", code="test_set_indem")
    admin_user.user_permissions.add(Permission.objects.get(codename="add_indemnification"))

    response = admin_client.post(f"/api/v1/organization/{org.pk}/indemnification/")
    assert response.status_code == 403
    assert not Indemnification.objects.filter(user=admin_user, organization=org).exists()


def test_set_indemnification_no_permission(admin_client, xtdb):
    org = Organization.objects.create(name="Test Org for No Perm", code="test_no_perm")

    response = admin_client.post(f"/api/v1/organization/{org.pk}/indemnification/")
    assert response.status_code == 403


def test_set_indemnification_already_exists(drf_client, organization_for_indemnification, user_with_indemnification):
    response = drf_client.post(f"/api/v1/organization/{organization_for_indemnification.pk}/indemnification/")
    assert response.status_code == 409

    result = response.json()
    assert result["indemnification"] is True
    assert result["user"] == user_with_indemnification.id
