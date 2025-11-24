import pytest
from django.db import IntegrityError
from pytest_django.asserts import assertContains

from plugins.models import BusinessRule
from plugins.views import (
    BusinessRuleCreateView,
    BusinessRuleDeleteView,
    BusinessRuleDetailView,
    BusinessRuleListView,
    BusinessRuleToggleView,
    BusinessRuleUpdateView,
)
from tests.conftest import setup_request


def test_business_rule_list_view(rf, superuser_member, xtdb):
    BusinessRule.objects.create(name="Test Rule 1", description="Test description 1", enabled=True)
    BusinessRule.objects.create(name="Test Rule 2", description="Test description 2", enabled=False)

    request = setup_request(rf.get("business_rule_list"), superuser_member.user)
    response = BusinessRuleListView.as_view()(request)

    assert response.status_code == 200
    assertContains(response, "Test Rule 1")
    assertContains(response, "Test Rule 2")
    assertContains(response, "Disable")
    assertContains(response, "Enable")


def test_business_rule_list_view_filtering(rf, superuser_member, xtdb):
    BusinessRule.objects.create(name="Enabled Rule", enabled=True)
    BusinessRule.objects.create(name="Disabled Rule", enabled=False)

    request = setup_request(rf.get("business_rule_list", {"enabled": "True"}), superuser_member.user)
    response = BusinessRuleListView.as_view()(request)

    assert response.status_code == 200
    assertContains(response, "Enabled Rule")


def test_business_rule_detail_view(rf, superuser_member, xtdb):
    rule = BusinessRule.objects.create(name="Test Rule", description="Test description", enabled=True)

    request = setup_request(rf.get("business_rule_detail", kwargs={"pk": rule.pk}), superuser_member.user)
    response = BusinessRuleDetailView.as_view()(request, pk=rule.pk)

    assert response.status_code == 200
    assertContains(response, "Test Rule")
    assertContains(response, "Test description")


def test_business_rule_create_view(rf, superuser_member, xtdb):
    request = setup_request(
        rf.post("add_business_rule", {"name": "New Rule", "description": "New description", "enabled": "on"}),
        superuser_member.user,
    )
    response = BusinessRuleCreateView.as_view()(request)

    assert response.status_code == 302
    assert BusinessRule.objects.filter(name="New Rule").exists()

    rule = BusinessRule.objects.get(name="New Rule")
    assert rule.description == "New description"
    assert rule.enabled is True


def test_business_rule_update_view(rf, superuser_member, xtdb):
    rule = BusinessRule.objects.create(name="Old Rule", description="Old description", enabled=False)
    request = setup_request(
        rf.post("edit_business_rule", {"name": "Updated Rule", "description": "Updated description", "enabled": "on"}),
        superuser_member.user,
    )
    response = BusinessRuleUpdateView.as_view()(request, pk=rule.pk)

    assert response.status_code == 302

    rule.refresh_from_db()
    assert rule.name == "Updated Rule"
    assert rule.description == "Updated description"
    assert rule.enabled is True


def test_business_rule_delete_view(rf, superuser_member, xtdb):
    rule = BusinessRule.objects.create(name="Rule to Delete", description="Will be deleted", enabled=True)

    rule_id = rule.pk
    request = setup_request(rf.post("delete_business_rule"), superuser_member.user)
    response = BusinessRuleDeleteView.as_view()(request, pk=rule_id)

    assert response.status_code == 302
    assert not BusinessRule.objects.filter(pk=rule_id).exists()


def test_business_rule_toggle_view_enable(rf, superuser_member, xtdb):
    rule = BusinessRule.objects.create(name="Disabled Rule", description="Will be enabled", enabled=False)

    request = setup_request(rf.post("toggle_business_rule", {"current_url": "/business-rules/"}), superuser_member.user)
    response = BusinessRuleToggleView.as_view()(request, pk=rule.pk)

    assert response.status_code == 302
    rule.refresh_from_db()
    assert rule.enabled is True

    messages = list(request._messages)
    assert len(messages) == 1
    assert "Disabled Rule" in str(messages[0])
    assert "enabled" in str(messages[0]).lower()


def test_business_rule_toggle_view_disable(rf, superuser_member, xtdb):
    rule = BusinessRule.objects.create(name="Enabled Rule", description="Will be disabled", enabled=True)

    request = setup_request(rf.post("toggle_business_rule", {"current_url": "/business-rules/"}), superuser_member.user)
    response = BusinessRuleToggleView.as_view()(request, pk=rule.pk)

    assert response.status_code == 302
    rule.refresh_from_db()
    assert rule.enabled is False

    messages = list(request._messages)
    assert len(messages) == 1
    assert "Enabled Rule" in str(messages[0])
    assert "disabled" in str(messages[0]).lower()


def test_business_rule_toggle_view_redirects_correctly(rf, superuser_member, xtdb):
    rule = BusinessRule.objects.create(name="Test Rule", enabled=True)

    request = setup_request(
        rf.post("toggle_business_rule", {"current_url": "/en/business-rules/"}), superuser_member.user
    )
    response = BusinessRuleToggleView.as_view()(request, pk=rule.pk)

    assert response.status_code == 302
    assert response.url == "/en/business-rules/"


@pytest.mark.django_db
def test_business_rule_created_and_updated_timestamps():
    rule = BusinessRule.objects.create(name="Timestamp Rule", enabled=True)

    assert rule.created_at is not None
    assert rule.updated_at is not None

    original_created_at = rule.created_at
    original_updated_at = rule.updated_at

    rule.name = "Updated Timestamp Rule"
    rule.save()

    assert rule.created_at == original_created_at
    assert rule.updated_at > original_updated_at


@pytest.mark.django_db
def test_business_rule_unique_name_constraint():
    BusinessRule.objects.create(name="Unique Rule", enabled=True)

    with pytest.raises(IntegrityError):
        BusinessRule.objects.create(name="Unique Rule", enabled=False)
