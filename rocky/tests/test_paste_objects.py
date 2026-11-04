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


def paste_request(rf, redteam_member, objects, step="1", network="internet", clearance_level=""):
    return setup_request(
        rf.post(
            "paste_objects", {"objects": objects, "network": network, "clearance_level": clearance_level, "step": step}
        ),
        redteam_member.user,
    )


def test_paste_objects_page(rf, redteam_member):
    request = setup_request(rf.get("paste_objects"), redteam_member.user)

    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)
    assert response.status_code == 200
    assertContains(response, "Paste objects")


def test_paste_objects_review_step(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """Step 1 renders the review page with the detected types; nothing is saved yet."""
    request = paste_request(rf, redteam_member, MIXED_BLOB)
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "Step 2 of 2")
    assertContains(response, "IPAddressV4")
    assertContains(response, "IPAddressV6")
    assertContains(response, "Hostname")
    assertContains(response, "URL")
    assert mock_organization_view_octopoes().save_many_declarations.call_count == 0


def test_paste_objects_mixed_blob(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """A single blob may contain IPv4, IPv6, hostnames and URLs at once."""
    request = paste_request(rf, redteam_member, MIXED_BLOB, step="2")
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
    """When nothing is valid, the review returns to step 1 with an error; nothing is saved."""
    request = paste_request(rf, redteam_member, "not_a_valid_host!!")
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "could not be created for line number(s): 1")
    assert mock_organization_view_octopoes().save_many_declarations.call_count == 0
    assert mock_bytes_client().add_manual_proof.call_count == 0


def test_paste_objects_invalid_input_step2(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """Submitting the review of an empty parse shows an error and saves nothing."""
    request = paste_request(rf, redteam_member, "not_a_valid_host!!", step="2")
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert mock_organization_view_octopoes().save_many_declarations.call_count == 0

    messages = list(request._messages)
    assert "could not be created for line number(s): 1" in messages[0].message


def test_paste_objects_partial_success(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """Invalid lines are listed on the review page; valid lines are still saved on submit."""
    request = paste_request(rf, redteam_member, PARTIAL_BLOB)
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "not a valid IP address, subnet, hostname or URL")
    assert mock_organization_view_octopoes().save_many_declarations.call_count == 0

    request = paste_request(rf, redteam_member, PARTIAL_BLOB, step="2")
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert mock_organization_view_octopoes().save_many_declarations.call_count == 1

    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    assert {declaration.ooi.object_type for declaration in declarations} == {"Network", "IPAddressV4"}


def test_paste_objects_clearance(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """A requested clearance level is raised for all parsed objects at once."""
    request = paste_request(rf, redteam_member, "example.com\n192.0.2.10", step="2", clearance_level="2")
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert mock_organization_view_octopoes().save_many_scan_profiles.call_count == 1


def test_paste_objects_separators(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """Values may be separated by commas and multiple values per line."""
    request = paste_request(rf, redteam_member, "192.0.2.10, 192.0.2.11 example.com", step="2")
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    assert len(declarations) == 4  # Network + 2 IPs + hostname


@pytest.mark.parametrize("network_name", ["internet", "darknet"])
def test_paste_objects_network(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client, network_name):
    request = paste_request(rf, redteam_member, "example.com", step="2", network=network_name)
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    network_declaration = next(declaration for declaration in declarations if declaration.ooi.object_type == "Network")
    assert network_declaration.ooi.name == network_name


def test_paste_objects_subnet(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """A CIDR becomes an IPV4NetBlock with its start IP declared alongside it."""
    request = paste_request(rf, redteam_member, "192.0.2.0/24\n2001:db8::/32", step="2")
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    object_types = [declaration.ooi.object_type for declaration in declarations]
    # Order matters: a start IP is declared before its netblock.
    assert object_types == ["Network", "IPAddressV4", "IPV4NetBlock", "IPAddressV6", "IPV6NetBlock"]

    netblock = next(declaration.ooi for declaration in declarations if declaration.ooi.object_type == "IPV4NetBlock")
    assert netblock.mask == 24
    assert netblock.start_ip.tokenized.address == "192.0.2.0"


def test_paste_objects_single_address_cidr(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """A /32 or /128 contains a single address and becomes an IP address object.

    This mirrors the rule enforced by the dedicated subnet form
    (SubnetAddForm) added on main.
    """
    request = paste_request(rf, redteam_member, "192.0.2.10/32", step="2")
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    assert {declaration.ooi.object_type for declaration in declarations} == {"Network", "IPAddressV4"}


def test_paste_objects_invalid_subnet(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """An invalid CIDR is reported per line, like other invalid values."""
    request = paste_request(rf, redteam_member, "192.0.2.0/33", step="2")
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert mock_organization_view_octopoes().save_many_declarations.call_count == 0
    messages = list(request._messages)
    assert "could not be created for line number(s): 1" in messages[0].message


def test_paste_objects_bracketed_ipv6(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """Bracketed IPv6, the notation used in URLs, is recognized as an address."""
    request = paste_request(rf, redteam_member, "[2001:db8::1]", step="2")
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    assert {declaration.ooi.object_type for declaration in declarations} == {"Network", "IPAddressV6"}
