from unittest.mock import ANY, call

from django.urls import resolve, reverse
from pytest_django.asserts import assertContains

from octopoes.models import Reference
from octopoes.models.tree import ReferenceTree
from rocky.views.ooi_tree import OOIGraphView
from tests.conftest import setup_request

TREE_DATA = {
    "root": {
        "reference": "Finding|Network|testnetwork|KAT-000",
        "children": {"ooi": [{"reference": "Network|testnetwork", "children": {}}]},
    },
    "store": {
        "Network|testnetwork": {"object_type": "Network", "primary_key": "Network|testnetwork", "name": "testnetwork"},
        "Finding|Network|testnetwork|KAT-000": {
            "object_type": "Finding",
            "primary_key": "Finding|Network|testnetwork|KAT-000",
            "ooi": "Network|testnetwork",
            "finding_type": "KATFindingType|KAT-000",
        },
    },
}


def test_ooi_graph(rf, client_member, mock_organization_view_octopoes):
    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(TREE_DATA)

    request = setup_request(rf.get("ooi_graph", {"ooi_id": "Network|testnetwork"}), client_member.user)
    request.resolver_match = resolve(
        reverse("ooi_graph", kwargs={"organization_code": client_member.organization.code})
    )
    response = OOIGraphView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    mock_organization_view_octopoes().get_tree.assert_has_calls(
        [
            call(Reference("Network|testnetwork"), valid_time=ANY, depth=2, with_scan_profiles=True, types=[]),
            call(Reference("Network|testnetwork"), valid_time=ANY, depth=9, with_scan_profiles=False, types=[]),
        ]
    )

    assertContains(response, "testnetwork")
    assertContains(response, "KAT-000")
