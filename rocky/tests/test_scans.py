import json
from pathlib import Path

from pytest_django.asserts import assertContains

from rocky.views.scans import ScanListView
from tests.conftest import setup_request


def test_katalogus_plugin_listing(client_member, rf, httpx_mock):
    httpx_mock.add_response(json=json.loads((Path(__file__).parent / "stubs" / "katalogus_boefjes.json").read_text()))

    request = setup_request(rf.get("scan_list"), client_member.user)
    response = ScanListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "Boefjes")
    assertContains(response, "BinaryEdge")
