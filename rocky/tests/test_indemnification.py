import pytest
from django.core.exceptions import PermissionDenied
from katalogus.views.change_clearance_level import ChangeClearanceLevel

from tests.conftest import setup_request


def test_update_clearance_level(rf, client_member, httpx_mock):
    httpx_mock.add_response(
        json={
            "id": "binaryedge",
            "name": "BinaryEdge",
            "version": None,
            "authors": None,
            "created": None,
            "description": "Use BinaryEdge to find open ports with vulnerabilities that are found on that port",
            "related": None,
            "enabled": True,
            "type": "boefje",
            "scan_level": 2,
            "consumes": ["IPAddressV6", "IPAddressV4"],
            "options": None,
            "produces": [
                "KATFindingType",
                "SoftwareInstance",
                "Service",
                "IPPort",
                "Finding",
                "Software",
                "IPService",
                "CVEFindingType",
            ],
        }
    )

    with pytest.raises(PermissionDenied):
        ChangeClearanceLevel.as_view()(
            setup_request(rf.get("change_clearance_level"), client_member.user),
            organization_code=client_member.organization.code,
            plugin_type="boefje",
            plugin_id="test-plugin",
            scan_level="1",
        )
