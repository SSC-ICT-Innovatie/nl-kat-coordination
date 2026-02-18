from pytest_django.asserts import assertContains

from rocky.views.finding_add import FindingAddView
from tests.conftest import setup_request


def test_findings_add(rf, client_member, mock_organization_view_octopoes):
    request = setup_request(rf.get("finding_add"), client_member.user)
    response = FindingAddView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "Add finding")
