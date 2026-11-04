import pytest
from pytest_django.asserts import assertContains

from rocky.views.paste_objects import PasteObjects
from tests.conftest import setup_request

MIXED_BLOB = """192.0.2.10
2001:db8::1
example.com
https://example.com/dashboard"""

PARTIAL_BLOB = """192.0.2.10
not_a_valid_host!!"""


def test_paste_objects_page(rf, redteam_member):
    request = setup_request(rf.get("paste_objects"), redteam_member.user)

    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)
    assert response.status_code == 200
    assertContains(response, "Paste objects")


def test_paste_objects_mixed_blob(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """A single blob may contain IPv4, IPv6, hostnames and URLs at once."""
    request = setup_request(
        rf.post("paste_objects", {"objects": MIXED_BLOB, "network": "internet", "clearance_level": ""}),
        redteam_member.user,
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert mock_organization_view_octopoes().save_declaration.call_count == 0
    assert mock_organization_view_octopoes().save_many_declarations.call_count == 1

    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    object_types = {declaration.ooi.object_type for declaration in declarations}
    assert object_types == {"Network", "IPAddressV4", "IPAddressV6", "Hostname", "URL"}

    task_id = mock_bytes_client().add_manual_proof.call_args[0][0]
    mock_bytes_client().add_manual_proof.assert_called_once_with(
        task_id, MIXED_BLOB.encode("utf-8"), manual_mime_types={"manual/txt"}
    )

    messages = list(request._messages)
    assert "successfully added" in messages[0].message


def test_paste_objects_invalid_input(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """When nothing is valid, nothing is saved and an error is shown."""
    request = setup_request(
        rf.post("paste_objects", {"objects": "not_a_valid_host!!", "network": "internet", "clearance_level": ""}),
        redteam_member.user,
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert mock_organization_view_octopoes().save_many_declarations.call_count == 0
    assert mock_bytes_client().add_manual_proof.call_count == 0

    messages = list(request._messages)
    assert "could not be created for line number(s): 1" in messages[0].message


def test_paste_objects_partial_success(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """Valid lines are saved even when other lines fail; errors report line numbers."""
    request = setup_request(
        rf.post("paste_objects", {"objects": PARTIAL_BLOB, "network": "internet", "clearance_level": ""}),
        redteam_member.user,
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert mock_organization_view_octopoes().save_many_declarations.call_count == 1

    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    assert {declaration.ooi.object_type for declaration in declarations} == {"Network", "IPAddressV4"}

    messages = list(request._messages)
    assert "could not be created for line number(s): 2" in messages[0].message
    assert "successfully added" in messages[1].message


def test_paste_objects_clearance(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """A requested clearance level is raised for all parsed objects at once."""
    request = setup_request(
        rf.post("paste_objects", {"objects": "example.com\n192.0.2.10", "network": "internet", "clearance_level": "2"}),
        redteam_member.user,
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert mock_organization_view_octopoes().save_many_scan_profiles.call_count == 1


def test_paste_objects_separators(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """Values may be separated by commas and multiple values per line."""
    request = setup_request(
        rf.post(
            "paste_objects",
            {"objects": "192.0.2.10, 192.0.2.11 example.com", "network": "internet", "clearance_level": ""},
        ),
        redteam_member.user,
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    assert len(declarations) == 4  # Network + 2 IPs + hostname


@pytest.mark.parametrize("network_name", ["internet", "darknet"])
def test_paste_objects_network(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client, network_name):
    request = setup_request(
        rf.post("paste_objects", {"objects": "example.com", "network": network_name, "clearance_level": ""}),
        redteam_member.user,
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    network_declaration = next(declaration for declaration in declarations if declaration.ooi.object_type == "Network")
    assert network_declaration.ooi.name == network_name
