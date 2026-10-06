import json
import uuid
from unittest.mock import Mock

from django import forms
from pytest_django.asserts import assertContains
from tools.forms.ooi_form import generate_select_ooi_field

from rocky.views.ooi_add import OOIAddView
from tests.conftest import setup_request


def test_add_ooi(rf, client_member, mock_organization_view_octopoes, mock_bytes_client):
    request = setup_request(rf.post("ooi_add", {"ooi_type": "Network", "name": "testnetwork"}), client_member.user)

    response = OOIAddView.as_view()(request, organization_code=client_member.organization.code, ooi_type="Network")

    assert response.status_code == 302
    assert response.url == "/en/test/objects/detail/?ooi_id=Network%7Ctestnetwork"

    mock_bytes_client().add_manual_proof.assert_called_once()
    call_args = mock_bytes_client().add_manual_proof.call_args[0]

    assert isinstance(call_args[0], uuid.UUID)

    actual = json.loads(call_args[1])
    expected_fragment = {
        "ooi": {
            "object_type": "Network",
            "scan_profile": None,
            "user_id": client_member.user.id,
            "primary_key": "Network|testnetwork",
            "name": "testnetwork",
        }
    }

    assert expected_fragment.items() <= actual[0].items()
    assert mock_organization_view_octopoes().save_declaration.call_count == 1


def test_add_bad_schema(rf, client_member):
    request = setup_request(
        rf.post("ooi_add", {"ooi_type": "Network", "testnamewrong": "testnetwork"}), client_member.user
    )

    response = OOIAddView.as_view()(request, organization_code=client_member.organization.code, ooi_type="Network")

    assert response.status_code == 200
    assertContains(response, "Error:")
    assertContains(response, "This field is required.")


def _mock_connector_with_oois(primary_keys: list[str]) -> Mock:
    connector = Mock()
    connector.list_objects.return_value = Mock(items=[Mock(primary_key=pk) for pk in primary_keys])
    return connector


def _required_single_select_field() -> Mock:
    field = Mock()
    field.is_required.return_value = True
    field.annotation = str  # not a list → single select
    return field


def test_select_ooi_field_preselects_when_single_required_option():
    """A required selector with exactly one available OOI is pre-selected."""
    connector = _mock_connector_with_oois(["Network|internet"])

    form_field = generate_select_ooi_field(connector, "network", _required_single_select_field(), Mock())

    assert form_field.initial == "Network|internet"


def test_select_ooi_field_no_preselect_when_multiple_options():
    """A required selector with more than one OOI is not pre-selected."""
    connector = _mock_connector_with_oois(["Network|internet", "Network|internal"])

    form_field = generate_select_ooi_field(connector, "network", _required_single_select_field(), Mock())

    assert form_field.initial is None


def test_select_ooi_field_accepts_value_outside_choices():
    """The select field is a CharField, not a ChoiceField, so it must accept
    OOI references beyond the (limit-50) choices list — the regression that
    broke finding-muting when ChoiceField was used."""
    connector = _mock_connector_with_oois(["Network|internet"])

    form_field = generate_select_ooi_field(connector, "network", _required_single_select_field(), Mock())

    assert isinstance(form_field, forms.CharField)
    assert not isinstance(form_field, forms.ChoiceField)
    assert form_field.clean("Network|not-in-choices") == "Network|not-in-choices"
