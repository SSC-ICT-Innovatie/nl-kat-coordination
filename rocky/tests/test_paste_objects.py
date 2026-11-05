import pytest
from pytest_django.asserts import assertContains, assertNotContains

from octopoes.models.exception import ObjectNotFoundException
from octopoes.models.ooi.network import Network
from rocky.views.paste_objects import PasteObjects
from tests.conftest import setup_request

MIXED_BLOB = """192.0.2.10
2001:db8::1
example.com
https://example.com/dashboard"""

PARTIAL_BLOB = """192.0.2.10
not_a_valid_host!!"""


def paste_request(
    rf,
    redteam_member,
    objects,
    step="1",
    network="internet",
    clearance_level="",
    networks=None,
    mock_organization_view_octopoes=None,
):
    if mock_organization_view_octopoes is not None:
        mock_organization_view_octopoes().list_objects.return_value.items = networks or []
    return setup_request(
        rf.post(
            "paste_objects", {"objects": objects, "network": network, "clearance_level": clearance_level, "step": step}
        ),
        redteam_member.user,
    )


def test_paste_objects_page(rf, redteam_member, mock_organization_view_octopoes):
    mock_organization_view_octopoes().list_objects.return_value.items = []

    request = setup_request(rf.get("paste_objects"), redteam_member.user)

    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)
    assert response.status_code == 200
    assertContains(response, "Paste objects")


def test_paste_objects_review_step(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """Step 1 renders the review page with the detected types; nothing is saved yet."""
    request = paste_request(
        rf, redteam_member, MIXED_BLOB, mock_organization_view_octopoes=mock_organization_view_octopoes
    )
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
    request = paste_request(
        rf, redteam_member, MIXED_BLOB, step="2", mock_organization_view_octopoes=mock_organization_view_octopoes
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert mock_organization_view_octopoes().save_declaration.call_count == 0
    assert mock_organization_view_octopoes().save_many_declarations.call_count == 1

    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    object_types = {declaration.ooi.object_type for declaration in declarations}
    # The network already exists (connector.get succeeds), so it is not redeclared.
    assert object_types == {"IPAddressV4", "IPAddressV6", "Hostname", "URL"}

    task_id = mock_bytes_client().add_manual_proof.call_args[0][0]
    mock_bytes_client().add_manual_proof.assert_called_once_with(
        task_id, MIXED_BLOB.encode("utf-8"), manual_mime_types={"manual/txt"}
    )

    messages = list(request._messages)
    assert "successfully added" in messages[0].message


def test_paste_objects_invalid_input(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """When nothing is valid, the review returns to step 1 with an error; nothing is saved."""
    request = paste_request(
        rf, redteam_member, "not_a_valid_host!!", mock_organization_view_octopoes=mock_organization_view_octopoes
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "could not be created for line number(s): 1")
    assert mock_organization_view_octopoes().save_many_declarations.call_count == 0
    assert mock_bytes_client().add_manual_proof.call_count == 0


def test_paste_objects_invalid_input_step2(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """Submitting the review of an empty parse shows an error and saves nothing."""
    request = paste_request(
        rf,
        redteam_member,
        "not_a_valid_host!!",
        step="2",
        mock_organization_view_octopoes=mock_organization_view_octopoes,
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert mock_organization_view_octopoes().save_many_declarations.call_count == 0

    messages = list(request._messages)
    assert "could not be created for line number(s): 1" in messages[0].message


def test_paste_objects_partial_success(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """Invalid lines are listed on the review page; valid lines are still saved on submit."""
    request = paste_request(
        rf, redteam_member, PARTIAL_BLOB, mock_organization_view_octopoes=mock_organization_view_octopoes
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "not a valid IP address, subnet, hostname or URL")
    assert mock_organization_view_octopoes().save_many_declarations.call_count == 0

    request = paste_request(
        rf, redteam_member, PARTIAL_BLOB, step="2", mock_organization_view_octopoes=mock_organization_view_octopoes
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert mock_organization_view_octopoes().save_many_declarations.call_count == 1

    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    assert {declaration.ooi.object_type for declaration in declarations} == {"IPAddressV4"}


def test_paste_objects_clearance(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """A requested clearance level is raised for all parsed objects at once."""
    request = paste_request(
        rf,
        redteam_member,
        "example.com\n192.0.2.10",
        step="2",
        clearance_level="2",
        mock_organization_view_octopoes=mock_organization_view_octopoes,
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert mock_organization_view_octopoes().save_many_scan_profiles.call_count == 1


def test_paste_objects_separators(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """Values may be separated by commas and multiple values per line."""
    request = paste_request(
        rf,
        redteam_member,
        "192.0.2.10, 192.0.2.11 example.com",
        step="2",
        mock_organization_view_octopoes=mock_organization_view_octopoes,
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    assert len(declarations) == 3  # 2 IPs + hostname; network exists so it is not redeclared


def test_paste_objects_duplicates_deduplicated(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """The same value pasted more than once yields one object (M2)."""
    request = paste_request(
        rf,
        redteam_member,
        "dup.example.com\ndup.example.com\nok.example.com",
        step="2",
        mock_organization_view_octopoes=mock_organization_view_octopoes,
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    names = [declaration.ooi.name for declaration in declarations if declaration.ooi.object_type == "Hostname"]
    assert sorted(names) == ["dup.example.com", "ok.example.com"]

    messages = list(request._messages)
    assert "2 × Hostname" in messages[0].message


def test_paste_objects_unknown_network_declared(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """If the selected network does not exist yet, it is declared first.

    The dropdown normally lists known networks, but a fresh organization
    may not have internet yet; the reference still has to resolve.
    """
    mock_organization_view_octopoes().get.side_effect = ObjectNotFoundException("not found")
    mock_organization_view_octopoes().list_objects.return_value.items = []

    request = paste_request(
        rf, redteam_member, "example.com", step="2", mock_organization_view_octopoes=mock_organization_view_octopoes
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    assert declarations[0].ooi.object_type == "Network"
    assert declarations[0].ooi.name == "internet"


@pytest.mark.parametrize("network_name", ["internet", "darknet"])
def test_paste_objects_network(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client, network_name):
    """Objects are declared in the network selected in step 1.

    Step 2 re-validates the network against the known networks, so the
    selected network must be one the connector lists (or internet).
    """
    mock_organization_view_octopoes().list_objects.return_value.items = [Network(name="darknet")]

    request = paste_request(
        rf,
        redteam_member,
        "example.com",
        step="2",
        network=network_name,
        networks=[Network(name="darknet")],
        mock_organization_view_octopoes=mock_organization_view_octopoes,
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    # The network reference is used for every object; the Network OOI
    # itself is only declared when absent, which test_paste_objects_
    # unknown_network_declared covers.
    assert all(
        declaration.ooi.network.tokenized.name == network_name
        for declaration in declarations
        if hasattr(declaration.ooi, "network")
    )


def test_paste_objects_network_choices(rf, redteam_member, mock_organization_view_octopoes):
    """The network dropdown lists known networks, with internet always available.

    Mirrors SubnetAddForm: choices come from list_objects on the
    connector, merged with a constant internet option.
    """
    networks = [Network(name=name) for name in ("darknet", "internet", "client-x")]
    mock_organization_view_octopoes().list_objects.return_value.items = networks

    request = setup_request(rf.get("paste_objects"), redteam_member.user)
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 200
    choices = [value for value, _label in response.context_data["form"].fields["network"].choices]
    assert choices == sorted({"internet", "darknet", "client-x"})


def test_paste_objects_subnet(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """A CIDR becomes an IPV4NetBlock with its start IP declared alongside it."""
    request = paste_request(
        rf,
        redteam_member,
        "192.0.2.0/24\n2001:db8::/32",
        step="2",
        mock_organization_view_octopoes=mock_organization_view_octopoes,
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    object_types = [declaration.ooi.object_type for declaration in declarations]
    # Order matters: a start IP is declared before its netblock. The
    # network already exists, so it is not redeclared.
    assert object_types == ["IPAddressV4", "IPV4NetBlock", "IPAddressV6", "IPV6NetBlock"]

    netblock = next(declaration.ooi for declaration in declarations if declaration.ooi.object_type == "IPV4NetBlock")
    assert netblock.mask == 24
    assert netblock.start_ip.tokenized.address == "192.0.2.0"


def test_paste_objects_single_address_cidr(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """A /32 or /128 contains a single address and becomes an IP address object.

    This mirrors the rule enforced by the dedicated subnet form
    (SubnetAddForm) added on main.
    """
    request = paste_request(
        rf, redteam_member, "192.0.2.10/32", step="2", mock_organization_view_octopoes=mock_organization_view_octopoes
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    assert {declaration.ooi.object_type for declaration in declarations} == {"IPAddressV4"}


def test_paste_objects_invalid_subnet(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """An invalid CIDR is reported per line, like other invalid values."""
    request = paste_request(
        rf, redteam_member, "192.0.2.0/33", step="2", mock_organization_view_octopoes=mock_organization_view_octopoes
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert mock_organization_view_octopoes().save_many_declarations.call_count == 0
    messages = list(request._messages)
    assert "could not be created for line number(s): 1" in messages[0].message


def test_paste_objects_subnet_notices(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """The review shows normalized subnets and warns for nmap-skipped ranges (M4)."""
    request = paste_request(
        rf, redteam_member, "10.0.0.5/8\n192.0.2.0/24", mock_organization_view_octopoes=mock_organization_view_octopoes
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 200
    # 10.0.0.5/8 has host bits: shown as interpreted, and 10.0.0.0/8 > /22
    assertContains(response, "interpreted as 10.0.0.0/8")
    assertContains(response, "nmap skips ranges larger than a /22 by default")
    # 192.0.2.0/24 is canonical and scannable: no notices
    assertNotContains(response, "interpreted as 192.0.2.0/24")


def test_paste_objects_bracketed_ipv6(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """Bracketed IPv6, the notation used in URLs, is recognized as an address."""
    request = paste_request(
        rf, redteam_member, "[2001:db8::1]", step="2", mock_organization_view_octopoes=mock_organization_view_octopoes
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    assert {declaration.ooi.object_type for declaration in declarations} == {"IPAddressV6"}


def test_paste_objects_single_label_hostname(rf, redteam_member, mock_organization_view_octopoes, mock_bytes_client):
    """Single-label names (aaaa, localhost) are valid hostnames, like everywhere else in OpenKAT.

    The Hostname model does not require a dot; the parser defers to it so
    all flows share one rule.
    """
    request = paste_request(
        rf, redteam_member, "aaaa\nlocalhost", step="2", mock_organization_view_octopoes=mock_organization_view_octopoes
    )
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    declarations = mock_organization_view_octopoes().save_many_declarations.call_args[0][0]
    hostnames = {declaration.ooi.name for declaration in declarations if declaration.ooi.object_type == "Hostname"}
    assert hostnames == {"aaaa", "localhost"}


def test_paste_objects_client_cannot_declare_clearance(
    rf, client_member, mock_organization_view_octopoes, mock_bytes_client
):
    """A member without tools.can_set_clearance_level cannot declare levels (H1).

    The clearance choices are empty for them, and a posted level is
    ignored instead of being declared.
    """
    client_member.acknowledged_clearance_level = 2
    client_member.trusted_clearance_level = 2
    client_member.save()

    mock_organization_view_octopoes().list_objects.return_value.items = []

    request = paste_request(
        rf,
        client_member,
        "example.com",
        step="2",
        clearance_level="2",
        mock_organization_view_octopoes=mock_organization_view_octopoes,
    )
    response = PasteObjects.as_view()(request, organization_code=client_member.organization.code)

    # The posted level is not even a valid choice for a client member,
    # so the form re-renders (back at step 1) and nothing is declared.
    assert response.status_code == 200
    assertNotContains(response, "Step 2 of 2")
    mock_organization_view_octopoes().save_many_scan_profiles.assert_not_called()
    mock_organization_view_octopoes().save_many_declarations.assert_not_called()


def test_paste_objects_clearance_choices_limited_by_max_level(rf, redteam_member, mock_organization_view_octopoes):
    """The clearance dropdown only offers levels up to the member's maximum (M1)."""
    redteam_member.acknowledged_clearance_level = 1
    redteam_member.trusted_clearance_level = 1
    redteam_member.save()

    mock_organization_view_octopoes().list_objects.return_value.items = []

    request = setup_request(rf.get("paste_objects"), redteam_member.user)
    response = PasteObjects.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 200
    choices = [value for value, _label in response.context_data["form"].fields["clearance_level"].choices]
    assert choices == ["", "0", "1"]
