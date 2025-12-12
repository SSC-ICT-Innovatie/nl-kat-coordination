import pytest

from openkat.management.commands.create_authtoken import create_auth_token
from openkat.models import Organization
from tests.conftest import JSONAPIClient


@pytest.fixture
def organizations(xtdb):
    return [
        Organization.objects.create(**org)
        for org in [{"name": "Test Organization 1", "tags": ["tag1", "tag2"]}, {"name": "Test Organization 2"}]
    ]


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

    org_map = {org["id"]: org for org in orgs_list}

    assert organizations[0].id in org_map
    assert org_map[organizations[0].id]["name"] == "Test Organization 1"
    assert sorted(org_map[organizations[0].id]["tags"]) == ["tag1", "tag2"]

    assert organizations[1].id in org_map
    assert org_map[organizations[1].id]["name"] == "Test Organization 2"


def test_create_organization(drf_client, xtdb):
    initial_count = Organization.objects.count()
    data = {"name": "Test Org 3", "tags": ["tag2", "tag3"]}

    response = drf_client.post("/api/v1/organization/", json=data)
    assert response.status_code == 201

    result = response.json()
    assert result["name"] == "Test Org 3"
    assert sorted(result["tags"]) == ["tag2", "tag3"]

    assert Organization.objects.count() == initial_count + 1
    org = Organization.objects.get(pk=result["id"])
    assert org.name == "Test Org 3"
    assert sorted(str(tag) for tag in org.tags.all()) == ["tag2", "tag3"]


def test_create_organization_no_permission(admin_client, admin_member, xtdb):
    data = {"name": "Test Org 3", "tags": ["tag2", "tag3"]}

    response = admin_client.post("/api/v1/organization/", json=data)
    assert response.status_code == 403


def test_retrieve_organization(admin_client, admin_member, organizations):
    org = organizations[0]
    response = admin_client.get(f"/api/v1/organization/{org.pk}/")
    assert response.status_code == 200

    result = response.json()
    assert result["id"] == org.pk
    assert result["name"] == "Test Organization 1"
    assert sorted(result["tags"]) == ["tag1", "tag2"]


def test_update_organization(drf_client, organizations):
    org = organizations[0]
    data = {"name": "Changed Organization", "tags": ["tag3", "tag4"]}

    response = drf_client.patch(f"/api/v1/organization/{org.pk}/", json=data)
    assert response.status_code == 200

    result = response.json()
    assert result["name"] == "Changed Organization"
    assert sorted(result["tags"]) == ["tag3", "tag4"]

    org.refresh_from_db()
    assert org.name == "Changed Organization"
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
