from pytest_django.asserts import assertContains

from rocky.views.finding_add import FindingAddView
from tests.conftest import setup_request


def test_findings_add(rf, client_member, mock_organization_view_octopoes, network):
    mock_organization_view_octopoes().get.return_value = network
    request = setup_request(rf.get("finding_add"), client_member.user)
    response = FindingAddView.as_view()(
        request, organization_code=client_member.organization.code, temporal_context=None, ooi="Network|testnetwork"
    )

    assert response.status_code == 200
    assertContains(response, "Add finding")
