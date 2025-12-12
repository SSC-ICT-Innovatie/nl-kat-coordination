from pytest_django.asserts import assertContains

from openkat.views.account import AccountView
from openkat.views.landing_page import LandingPageView
from tests.conftest import setup_request


def test_landing_page_redirect(rf, client_member):
    request = setup_request(rf.get("landing_page"), client_member.user)

    response = LandingPageView.as_view()(request)
    assert response.status_code == 302  # Redirects to crisis-room


def test_language_lang_attribute(rf, client_member, language):
    response = AccountView.as_view()(
        setup_request(rf.get("account_detail"), client_member.user), organization_id=client_member.organization.id
    )
    assert response.status_code == 200
    assertContains(response, '<html lang="' + language + '"')
