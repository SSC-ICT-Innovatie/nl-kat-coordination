import pytest
from django.test import Client
from django.urls import reverse

from openkat.models import AuthToken, Organization, User


@pytest.fixture
def admin_client(superuser):
    """Create a Django test client logged in as superuser."""
    client = Client()
    client.force_login(superuser)
    return client


@pytest.fixture
def auth_token(superuser):
    """Create a test AuthToken instance."""
    token = AuthToken(user=superuser, name="Test Token")
    token.generate_new_token()
    token.save()
    return token


def test_organization_admin_add_view(admin_client, xtdb):
    """Test the Organization admin add view."""
    url = reverse("admin:openkat_organization_add")

    # Test GET request shows add form
    response = admin_client.get(url)
    assert response.status_code == 200
    assert "name" in response.content.decode()

    # Test POST with valid data creates organization
    data = {"name": "New Organization", "tags": ""}
    response = admin_client.post(url, data)
    assert response.status_code == 302  # Redirect after successful creation

    # Verify organization was created in PostgreSQL
    Organization.objects.get(name="New Organization")


def test_organization_admin_change_view(admin_client, organization, xtdb):
    """Test the Organization admin change view."""
    url = reverse("admin:openkat_organization_change", args=[organization.pk])

    # Test GET request shows change form with existing data
    response = admin_client.get(url)
    assert response.status_code == 200
    assert organization.name in response.content.decode()

    # Test POST updates organization name
    data = {"name": "Updated Organization Name", "tags": ""}
    response = admin_client.post(url, data)
    assert response.status_code == 302  # Redirect after successful update

    # Verify changes persisted
    organization.refresh_from_db()
    assert organization.name == "Updated Organization Name"


def test_organization_admin_delete_view(admin_client, organization, xtdb):
    """Test the Organization admin delete view."""
    url = reverse("admin:openkat_organization_delete", args=[organization.pk])

    # Test GET shows delete confirmation page
    response = admin_client.get(url)
    assert response.status_code == 200
    assert "Are you sure" in response.content.decode()
    assert organization.name in response.content.decode()

    # Test POST successfully deletes organization
    response = admin_client.post(url, {"post": "yes"})
    assert response.status_code == 302  # Redirect after successful deletion

    # Verify organization was deleted
    assert not Organization.objects.filter(pk=organization.pk).exists()


def test_organization_admin_changelist_view(admin_client, organization, xtdb):
    """Test the Organization admin changelist view."""
    # Create additional organizations for testing
    org2 = Organization.objects.create(name="Second Org")
    org3 = Organization.objects.create(name="Third Org")

    url = reverse("admin:openkat_organization_changelist")

    # Test GET request shows list of organizations
    response = admin_client.get(url)
    assert response.status_code == 200

    content = response.content.decode()
    # Verify list displays correct columns (name, code, tags)
    assert organization.name in content
    assert org2.name in content
    assert org3.name in content

    # Verify table headers are present (list_display fields)
    assert "Name" in content


def test_authtoken_admin_add_view(admin_client, superuser):
    """Test the AuthToken admin add view."""
    url = reverse("admin:openkat_authtoken_add")

    # Test GET request shows add form
    response = admin_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "name" in content.lower()
    assert "user" in content.lower()
    assert "expiry" in content.lower()

    # Test POST with valid data creates token
    data = {"user": superuser.pk, "name": "Test API Token", "expiry": "2025-12-31 23:59:59"}
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200

    # Verify token was created
    token = AuthToken.objects.get(user=superuser, name="Test API Token")
    assert token.user == superuser
    assert token.name == "Test API Token"
    assert token.token_key is not None

    # Check that the token value is shown in a message
    messages = list(response.context["messages"])
    assert any("The new token is:" in str(message) for message in messages)

    # Test unique constraint validation (same user + name combination)
    response = admin_client.post(url, data)
    assert response.status_code == 200
    content = response.content.decode()
    assert "already exists" in content.lower() or "unique" in content.lower()


def test_authtoken_admin_change_view(admin_client, auth_token):
    """Test the AuthToken admin change view."""
    url = reverse("admin:openkat_authtoken_change", args=[auth_token.pk])

    # Test GET request shows change form with existing data
    response = admin_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert auth_token.name in content
    assert str(auth_token.user) in content
    # Note: token_key is not shown in change form, only in list view

    # Test POST updates token name without regenerating token
    original_token_key = auth_token.token_key
    data = {
        "user": auth_token.user.pk,
        "name": "Updated Token Name",
        "expiry": (auth_token.expiry.strftime("%Y-%m-%d %H:%M:%S") if auth_token.expiry else ""),
    }
    response = admin_client.post(url, data)
    assert response.status_code == 302  # Redirect after successful update

    # Verify changes persisted and token_key unchanged
    auth_token.refresh_from_db()
    assert auth_token.name == "Updated Token Name"
    assert auth_token.token_key == original_token_key  # Should not regenerate


def test_authtoken_admin_delete_view(admin_client, auth_token):
    """Test the AuthToken admin delete view."""
    url = reverse("admin:openkat_authtoken_delete", args=[auth_token.pk])

    # Test GET shows delete confirmation page
    response = admin_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Are you sure" in content
    assert auth_token.name in content
    assert str(auth_token.user) in content

    # Test POST successfully deletes token
    response = admin_client.post(url, {"post": "yes"})
    assert response.status_code == 302  # Redirect after successful deletion

    # Verify token was deleted
    assert not AuthToken.objects.filter(pk=auth_token.pk).exists()


def test_authtoken_admin_changelist_view(admin_client, auth_token, superuser):
    """Test the AuthToken admin changelist view."""
    # Create additional tokens for testing
    token2 = AuthToken(user=superuser, name="Second Token")
    token2.generate_new_token()
    token2.save()

    # Create another user and token
    user2 = User.objects.create_user(email="user2@example.com", password="pass123", full_name="User Two")
    token3 = AuthToken(user=user2, name="User2 Token")
    token3.generate_new_token()
    token3.save()

    url = reverse("admin:openkat_authtoken_changelist")

    # Test GET request shows list of tokens
    response = admin_client.get(url)
    assert response.status_code == 200

    content = response.content.decode()
    # Verify list displays tokens
    assert auth_token.name in content
    assert token2.name in content
    assert token3.name in content
    assert str(superuser) in content
    assert str(user2) in content

    # Verify table headers are present (list_display fields)
    assert "User" in content
    assert "Name" in content
    assert "Token key" in content
    assert "Created" in content
