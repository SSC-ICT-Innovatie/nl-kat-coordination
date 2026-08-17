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


def test_ooi_graph_tree_is_hydrated_with_display_name(rf, client_member, mock_organization_view_octopoes):
    # Regression for #5322: the graph reads d.data.display_name for every node.
    # OOIGraphView must expose a hydrated `graph_tree`, otherwise display_name is missing
    # and the d3 render crashes in truncateText(undefined).
    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(TREE_DATA)

    request = setup_request(rf.get("ooi_graph", {"ooi_id": "Network|testnetwork"}), client_member.user)
    request.resolver_match = resolve(
        reverse("ooi_graph", kwargs={"organization_code": client_member.organization.code})
    )
    response = OOIGraphView.as_view()(request, organization_code=client_member.organization.code)

    # hydrate_branch adds display_name (from human_readable), name and graph_url to
    # every node; without the hydrated tree in the context these keys are missing and
    # the d3 render crashes in truncateText(undefined).
    def assert_hydrated(node):
        assert node["display_name"] == node["human_readable"]
        assert "graph_url" in node
        for child in node.get("children", []):
            assert_hydrated(child)

    assert_hydrated(response.context_data["graph_tree"])

    # The hydration lives on `graph_tree` only; the shared `tree` context (used by the
    # tree/summary tabs) must stay filter-only so those tabs don't pay for graph fields.
    def assert_not_hydrated(node):
        assert "display_name" not in node
        assert "graph_url" not in node
        for child in node.get("children", []):
            assert_not_hydrated(child)

    assert_not_hydrated(response.context_data["tree"])
