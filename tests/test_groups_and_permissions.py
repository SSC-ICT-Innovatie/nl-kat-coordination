from pytest_django.asserts import assertContains, assertNotContains

from openkat.views.account import AccountView
from tests.conftest import setup_request


def test_account_detail_perms(rf, superuser_member, admin_member, client_member):
    response_superuser = AccountView.as_view()(
        setup_request(rf.get("account_detail"), superuser_member.user), organization_id=superuser_member.organization.id
    )

    response_admin = AccountView.as_view()(
        setup_request(rf.get("account_detail"), admin_member.user), organization_id=admin_member.organization.id
    )

    response_client = AccountView.as_view()(
        setup_request(rf.get("account_detail"), client_member.user), organization_id=client_member.organization.id
    )
    assert response_superuser.status_code == 200
    assert response_admin.status_code == 200
    assert response_client.status_code == 200

    # There is already text having clearance outside the perms sections, so header tags must be included
    check_text = "<h2>Object Clearance</h2>"

    assertContains(response_superuser, check_text)
    assertNotContains(response_admin, check_text)
    assertNotContains(response_client, check_text)
