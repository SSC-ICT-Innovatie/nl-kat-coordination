import pytest
from pytest_django.asserts import assertContains

from onboarding.views import OnboardingIntroductionView
from tests.conftest import setup_request


@pytest.mark.django_db(databases=["xtdb", "default"])
@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "client_member"])
def test_onboarding_introduction(request, member, rf):
    member = request.getfixturevalue(member)
    response = OnboardingIntroductionView.as_view()(
        setup_request(rf.get("step_introduction"), member.user), organization_code=member.organization.code
    )

    assert response.status_code == 200
    assertContains(response, "Welcome to OpenKAT")
    assertContains(response, "Skip onboarding")
    assertContains(response, "Let's get started")
