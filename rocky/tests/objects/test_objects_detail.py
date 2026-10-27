from copy import deepcopy
from urllib.parse import urlencode

import pytest
from django.template.loader import render_to_string
from katalogus.client import Boefje
from pytest_django.asserts import assertContains, assertNotContains
from tools.enums import SCAN_LEVEL
from tools.models import Indemnification
from tools.ooi_helpers import finding_display_proof, format_display, is_legacy_tls_cipher_finding

from octopoes.connector import RemoteException
from octopoes.models.exception import ObjectNotFoundException
from octopoes.models.ooi.config import Config
from octopoes.models.ooi.findings import Finding
from octopoes.models.tree import ReferenceTree
from rocky.views.ooi_detail import OOIDetailView
from tests.conftest import get_stub_path, setup_request

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

QUESTION_DATA = {
    "root": {
        "reference": "Question|/test|Network|testnetwork",
        "children": {"ooi": [{"reference": "Network|testnetwork", "children": {}}]},
    },
    "store": {
        "Network|testnetwork": {"object_type": "Network", "primary_key": "Network|testnetwork", "name": "testnetwork"},
        "Question|/test|Network|testnetwork": {
            "ooi": "Network|testnetwork",
            "object_type": "Question",
            "schema_id": "/test",
            "json_schema": get_stub_path("question_schema.json").read_text(),
            "primary_key": "Question|/test|Network|testnetwork",
        },
    },
}


def test_ooi_detail(rf, client_member, mock_organization_view_octopoes, mock_scheduler, paginated_task_list, mocker):
    mocker.patch("katalogus.client.KATalogusClient")

    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(TREE_DATA)

    mock_scheduler.list_tasks.return_value = paginated_task_list

    request = setup_request(rf.get("ooi_detail", {"ooi_id": "Network|testnetwork"}), client_member.user)

    response = OOIDetailView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assert mock_organization_view_octopoes().get_tree.call_count == 1
    assertContains(response, "Object")
    assertContains(response, "Network|testnetwork")

    assertContains(response, "Plugin")
    assertContains(response, "TestBoefje")
    assertContains(
        response, f'href="/en/{client_member.organization.code}/kat-alogus/plugins/boefje/test-boefje/">TestBoefje</a>'
    )
    assertContains(response, "Status")
    assertContains(response, "Completed")
    assertContains(response, "Created date")
    assertContains(response, "9, 2022, 11:53 a.m.")
    assertNotContains(response, "Question")
    assertNotContains(response, "Fill out this form to answer the Question (again)")


def test_question_detail(
    rf, client_member, mock_organization_view_octopoes, mock_scheduler, paginated_task_list, mocker
):
    mocker.patch("katalogus.client.KATalogusClient")

    request = setup_request(rf.get("ooi_detail", {"ooi_id": "Question|/test|Network|testnetwork"}), client_member.user)

    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(QUESTION_DATA)
    # No saved answer: the Config lookup 404s.
    mock_organization_view_octopoes().get.side_effect = ObjectNotFoundException("Config not found")

    response = OOIDetailView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assert mock_organization_view_octopoes().get_tree.call_count == 1

    assertContains(response, "Question")
    assertContains(response, "Fill out this form to answer the Question (again)")
    assertContains(response, "Submit")


def test_question_detail_prefills_saved_config(
    rf, client_member, mock_organization_view_octopoes, mock_scheduler, paginated_task_list, mocker
):
    mocker.patch("katalogus.client.KATalogusClient")

    question_data = deepcopy(QUESTION_DATA)
    question_data["store"]["Question|/test|Network|testnetwork"]["ooi"] = "Network|testnetwork"
    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(question_data)
    mock_organization_view_octopoes().get.return_value = Config(
        ooi="Network|testnetwork", bit_id="/test", config={"key": "value"}
    )

    request = setup_request(rf.get("ooi_detail", {"ooi_id": "Question|/test|Network|testnetwork"}), client_member.user)

    response = OOIDetailView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "Using config from")
    assertContains(response, 'data-original="{&quot;key&quot;: &quot;value&quot;}"')


def test_question_detail_empty_config_still_loads_saved_answer(
    rf, client_member, mock_organization_view_octopoes, mock_scheduler, paginated_task_list, mocker
):
    """An empty saved Config is a saved answer: it must render data-original
    instead of silently falling back to the schema defaults."""
    mocker.patch("katalogus.client.KATalogusClient")

    question_data = deepcopy(QUESTION_DATA)
    question_data["store"]["Question|/test|Network|testnetwork"]["ooi"] = "Network|testnetwork"
    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(question_data)
    mock_organization_view_octopoes().get.return_value = Config(ooi="Network|testnetwork", bit_id="/test", config={})

    request = setup_request(rf.get("ooi_detail", {"ooi_id": "Question|/test|Network|testnetwork"}), client_member.user)

    response = OOIDetailView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "Using config from")
    assertContains(response, 'data-original="{}"')


def test_question_detail_config_lookup_error_is_not_shown_as_unanswered(
    rf, client_member, mock_organization_view_octopoes, mock_scheduler, paginated_task_list, mocker
):
    """Only a missing Config means "unanswered"; an Octopoes failure must not be rendered as one."""
    mocker.patch("katalogus.client.KATalogusClient")

    question_data = deepcopy(QUESTION_DATA)
    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(question_data)
    mock_organization_view_octopoes().get.side_effect = RemoteException("Octopoes unavailable")

    request = setup_request(rf.get("ooi_detail", {"ooi_id": "Question|/test|Network|testnetwork"}), client_member.user)

    with pytest.raises(RemoteException):
        OOIDetailView.as_view()(request, organization_code=client_member.organization.code)


def test_answer_question(
    rf,
    client_member,
    mock_scheduler,
    mock_bytes_client,
    mock_organization_view_octopoes,
    lazy_task_list_with_boefje,
    mocker,
):
    mocker.patch("katalogus.client.KATalogusClient")
    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(QUESTION_DATA)
    mock_organization_view_octopoes().get.side_effect = ObjectNotFoundException("Config not found")

    query_string = urlencode({"ooi_id": "Question|/test|Network|testnetwork"}, doseq=True)
    request = setup_request(
        rf.post(
            f"/en/{client_member.organization.code}/objects/details/?{query_string}",
            data={"schema": '{"key": "value", "sa_tcp_ports": "314159,23"}', "action": "submit_answer"},
        ),
        client_member.user,
    )
    response = OOIDetailView.as_view()(request, organization_code=client_member.organization.code)

    assertContains(response, "Question has been answered.", status_code=200)
    assert mock_organization_view_octopoes().get_tree.call_count == 1


def test_answer_question_bad_schema(
    rf,
    client_member,
    mock_scheduler,
    mock_bytes_client,
    mock_organization_view_octopoes,
    lazy_task_list_with_boefje,
    mocker,
):
    mocker.patch("katalogus.client.KATalogusClient")
    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(QUESTION_DATA)
    mock_organization_view_octopoes().get.side_effect = ObjectNotFoundException("Config not found")

    query_string = urlencode({"ooi_id": "Question|/test|Network|testnetwork"}, doseq=True)

    request = setup_request(
        rf.post(
            f"/en/{client_member.organization.code}/objects/details/?{query_string}",
            data={"schema": '{"key": "value", "sa_tcp_ports": 314159}', "action": "submit_answer"},
        ),
        client_member.user,
    )
    response = OOIDetailView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200

    quote_enc = "&#x27;"
    assertContains(response, f"314159 is not of type {quote_enc}string{quote_enc}", status_code=200)


def test_ooi_detail_start_scan(
    rf, client_member, mock_organization_view_octopoes, mock_scheduler, paginated_task_list, mocker, network
):
    mock_katalogus = mocker.patch("katalogus.client.KATalogusClient")

    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(TREE_DATA)
    mock_organization_view_octopoes().get.return_value = network

    mock_katalogus().get_plugin.return_value = Boefje(
        id="nmap",
        name="",
        description="",
        enabled=True,
        type="boefje",
        scan_level=SCAN_LEVEL.L2,
        consumes=[],
        produces=[],
    )

    # Passing query params in POST requests is not well-supported for RequestFactory it seems, hence the absolute path
    query_string = urlencode({"ooi_id": network.reference}, doseq=True)

    request = setup_request(
        rf.post(
            f"/en/{client_member.organization.code}/objects/details/?{query_string}",
            data={"boefje_id": "nmap", "action": "start_scan"},
        ),
        client_member.user,
    )
    response = OOIDetailView.as_view()(request, organization_code=client_member.organization.code)

    assert mock_organization_view_octopoes().get_tree.call_count == 1

    assert response.status_code == 200


def test_ooi_detail_start_scan_no_indemnification(
    rf, client_member, mock_organization_view_octopoes, mock_scheduler, paginated_task_list, mocker, network
):
    mocker.patch("katalogus.client.KATalogusClient")

    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(TREE_DATA)
    mock_organization_view_octopoes().get.return_value = network
    mock_katalogus = mocker.patch("katalogus.client.KATalogusClient")
    mock_katalogus().get_plugin.return_value = Boefje(
        id="nmap",
        name="",
        description="",
        enabled=True,
        type="boefje",
        scan_level=SCAN_LEVEL.L2,
        consumes=[],
        produces=[],
    )

    Indemnification.objects.get(user=client_member.user).delete()

    # Passing query params in POST requests is not well-supported for RequestFactory it seems, hence the absolute path
    query_string = urlencode({"ooi_id": network.reference}, doseq=True)
    request = setup_request(
        rf.post(
            f"/en/{client_member.organization.code}/objects/details/?{query_string}",
            data={"boefje_id": "test-boefje", "action": "start_scan"},
        ),
        client_member.user,
    )
    response = OOIDetailView.as_view()(request, organization_code=client_member.organization.code)

    assert mock_organization_view_octopoes().get_tree.call_count == 1
    assertContains(response, "Object details")
    assertContains(response, "Indemnification not present")


def test_ooi_detail_start_scan_no_action(
    rf, client_member, mock_scheduler, mock_organization_view_octopoes, lazy_task_list_with_boefje, mocker, network
):
    mocker.patch("katalogus.client.KATalogusClient")

    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(TREE_DATA)
    mock_organization_view_octopoes().get.return_value = network

    # Passing query params in POST requests is not well-supported for RequestFactory it seems, hence the absolute path
    query_string = urlencode({"ooi_id": network.reference}, doseq=True)
    request = setup_request(
        rf.post(f"/en/{client_member.organization.code}/objects/details/?{query_string}", data={"boefje_id": "nmap"}),
        client_member.user,
    )
    response = OOIDetailView.as_view()(request, organization_code=client_member.organization.code)

    assert mock_organization_view_octopoes().get_tree.call_count == 1
    assertContains(response, "Object details")


@pytest.mark.parametrize("member", ["superuser_member", "admin_member", "redteam_member"])
def test_delete_perms_ooi_detail(
    request, member, rf, mock_scheduler, mock_organization_view_octopoes, lazy_task_list_with_boefje, mocker
):
    member = request.getfixturevalue(member)
    mocker.patch("katalogus.client.KATalogusClient")
    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(TREE_DATA)
    mock_scheduler.get_lazy_task_list.return_value = lazy_task_list_with_boefje

    response = OOIDetailView.as_view()(
        setup_request(rf.get("ooi_detail", {"ooi_id": "Network|testnetwork"}), member.user),
        organization_code=member.organization.code,
    )

    assert response.status_code == 200
    assertContains(response, "Delete")


def test_delete_perms_ooi_detail_clients(
    rf, client_member, mock_scheduler, mock_organization_view_octopoes, lazy_task_list_with_boefje, mocker
):
    mocker.patch("katalogus.client.KATalogusClient")
    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(TREE_DATA)
    mock_scheduler.get_lazy_task_list.return_value = lazy_task_list_with_boefje

    response = OOIDetailView.as_view()(
        setup_request(rf.get("ooi_detail", {"ooi_id": "Network|testnetwork"}), client_member.user),
        organization_code=client_member.organization.code,
    )
    assert response.status_code == 200
    assertNotContains(response, "Delete")


def test_ooi_detail_start_scan_perms(
    rf, client_member, mock_scheduler, mock_organization_view_octopoes, lazy_task_list_with_boefje, mocker
):
    mocker.patch("katalogus.client.KATalogusClient")
    request = setup_request(rf.get("ooi_detail", {"ooi_id": "Network|testnetwork"}), client_member.user)

    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(TREE_DATA)
    mock_scheduler.get_lazy_task_list.return_value = lazy_task_list_with_boefje

    response = OOIDetailView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assertNotContains(response, "Start Scan")


def test_legacy_cipher_finding_is_displayed_under_proof(
    rf, client_member, mock_organization_view_octopoes, mock_scheduler, paginated_task_list, mocker
):
    """Previously stored TLS cipher findings must work without being scanned again."""
    mocker.patch("katalogus.client.KATalogusClient")
    mock_scheduler.list_tasks.return_value = paginated_task_list

    cipher_reference = "Finding|Network|testnetwork|KAT-MEDIUM-TLS-CIPHER"
    tree = deepcopy(TREE_DATA)
    old_reference = tree["root"]["reference"]
    tree["root"]["reference"] = cipher_reference
    cipher = tree["store"].pop(old_reference)
    cipher.update(
        primary_key=cipher_reference,
        finding_type="KATFindingType|KAT-MEDIUM-TLS-CIPHER",
        description=(
            "One or more of the cipher suites should not be used because:\n"
            "Cipher A - weak key exchange (Low).\n"
            "Cipher B - insecure <algorithm> (Medium)."
        ),
    )
    tree["store"][cipher_reference] = cipher
    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(tree)

    request = setup_request(rf.get("ooi_detail", {"ooi_id": cipher_reference}), client_member.user)
    response = OOIDetailView.as_view()(request, organization_code=client_member.organization.code)

    assertContains(response, "Proof")
    assertContains(response, "Cipher A - weak key exchange.<br>Cipher B - insecure &lt;algorithm&gt;.", html=False)
    assertNotContains(response, "(Low)")
    assertNotContains(response, "<dt>Description</dt>", html=False)


def test_non_cipher_description_does_not_move_to_proof(
    rf, client_member, mock_organization_view_octopoes, mock_scheduler, paginated_task_list, mocker
):
    mocker.patch("katalogus.client.KATalogusClient")
    mock_scheduler.list_tasks.return_value = paginated_task_list
    tree = deepcopy(TREE_DATA)
    tree["store"]["Finding|Network|testnetwork|KAT-000"]["description"] = (
        "One or more of the cipher suites should not be used because:\nNot a TLS cipher finding"
    )
    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(tree)

    request = setup_request(rf.get("ooi_detail", {"ooi_id": "Finding|Network|testnetwork|KAT-000"}), client_member.user)
    response = OOIDetailView.as_view()(request, organization_code=client_member.organization.code)

    assertContains(response, "Description")
    assertContains(response, "Not a TLS cipher finding")
    assert response.context_data["object_details"]["Proof"] is None


def test_finding_occurrence_legacy_cipher_proof_renders_without_duplicate_description():
    finding = Finding(
        finding_type="KATFindingType|KAT-LOW-TLS-CIPHER",
        ooi="Network|testnetwork",
        description=(
            "One or more of the cipher suites should not be used because:\n"
            "Cipher A (Low).\n"
            "Cipher B <unsafe> (High)."
        ),
    )
    html = render_to_string("partials/finding_occurrence_definition_list.html", {"finding": finding})

    assert "Proof" in html
    assert "Cipher A.<br>Cipher B &lt;unsafe&gt;." in html
    assert "(Low)" not in html
    assert "Description" not in html


def test_new_cipher_finding_keeps_existing_description_and_proof():
    finding = Finding(
        finding_type="KATFindingType|KAT-LOW-TLS-CIPHER",
        ooi="Network|testnetwork",
        description="A separate explanation",
        proof="Cipher A\nCipher B <unsafe>",
    )
    assert not is_legacy_tls_cipher_finding(finding)
    html = render_to_string(
        "oois/ooi_detail_object.html",
        {"object_details": format_display({"description": finding.description, "proof": finding.proof})},
    )
    assert "A separate explanation" in html
    assert "Cipher A<br>Cipher B &lt;unsafe&gt;" in html


def test_historical_cipher_proof_severity_is_only_hidden_for_cipher_evidence():
    text = (
        "One or more of the cipher suites should not be used because:\n"
        "DHE-RSA-AES256-SHA - Using CBC as bulk encryption algorithm (Low).\n"
        "Another cipher - Using an algorithm (High).\n"
        "A note (experimental)."
    )
    stored_proof = Finding(finding_type="KATFindingType|KAT-LOW-TLS-CIPHER", ooi="Network|testnetwork", proof=text)
    expected = (
        "One or more of the cipher suites should not be used because:\n"
        "DHE-RSA-AES256-SHA - Using CBC as bulk encryption algorithm.\n"
        "Another cipher - Using an algorithm.\n"
        "A note (experimental)."
    )
    assert finding_display_proof(stored_proof) == expected
    assert stored_proof.proof == text  # Stored data stays untouched.

    unrelated = Finding(finding_type="KATFindingType|KAT-000", ooi="Network|testnetwork", proof=text)
    assert finding_display_proof(unrelated) == text


def test_cipher_proof_with_stored_severity_renders_without_suffix():
    finding = Finding(
        finding_type="KATFindingType|KAT-LOW-TLS-CIPHER",
        ooi="Network|testnetwork",
        proof=(
            "One or more of the cipher suites should not be used because:\n"
            "DHE-RSA-AES256-SHA - Using CBC as bulk encryption algorithm (Low).\n"
            "A second <cipher> (Low)."
        ),
    )
    html = render_to_string("partials/finding_occurrence_definition_list.html", {"finding": finding})
    assert "DHE-RSA-AES256-SHA - Using CBC as bulk encryption algorithm.<br>A second &lt;cipher&gt;." in html
    assert "(Low)" not in html


def test_ooi_detail_object_proof_displays_each_cipher_finding_on_a_new_line():
    html = render_to_string(
        "oois/ooi_detail_object.html",
        {
            "object_details": {
                "Description": "General finding description",
                "Proof": "Cipher A - weak key exchange\nCipher B - insecure <algorithm>",
            }
        },
    )

    assert "General finding description" in html
    assert "Cipher A - weak key exchange<br>Cipher B - insecure &lt;algorithm&gt;" in html


def test_finding_occurrence_proof_displays_each_cipher_finding_on_a_new_line():
    finding = Finding(
        finding_type="KATFindingType|KAT-LOW-TLS-CIPHER",
        ooi="Network|testnetwork",
        proof="Cipher A - weak key exchange\nCipher B - insecure <algorithm>",
    )

    html = render_to_string("partials/finding_occurrence_definition_list.html", {"finding": finding})

    assert "Cipher A - weak key exchange<br>Cipher B - insecure &lt;algorithm&gt;" in html


def test_cipher_finding_merged_after_rescan_hides_stale_description(
    rf, client_member, mock_organization_view_octopoes, mock_scheduler, paginated_task_list, mocker
):
    """Octopoes keeps the old description when the bit re-infers the finding with only `proof` set."""
    mocker.patch("katalogus.client.KATalogusClient")
    mock_scheduler.list_tasks.return_value = paginated_task_list

    cipher_reference = "Finding|Network|testnetwork|KAT-MEDIUM-TLS-CIPHER"
    tree = deepcopy(TREE_DATA)
    old_reference = tree["root"]["reference"]
    tree["root"]["reference"] = cipher_reference
    cipher = tree["store"].pop(old_reference)
    cipher.update(
        primary_key=cipher_reference,
        finding_type="KATFindingType|KAT-MEDIUM-TLS-CIPHER",
        description="One or more of the cipher suites should not be used because:\nCipher A - removed suite (Medium).",
        proof="One or more of the cipher suites should not be used because:\nCipher B - current suite.",
    )
    tree["store"][cipher_reference] = cipher
    mock_organization_view_octopoes().get_tree.return_value = ReferenceTree.model_validate(tree)

    request = setup_request(rf.get("ooi_detail", {"ooi_id": cipher_reference}), client_member.user)
    response = OOIDetailView.as_view()(request, organization_code=client_member.organization.code)

    assertContains(response, "Cipher B - current suite.")
    assertNotContains(response, "Cipher A - removed suite")
    assertNotContains(response, "<dt>Description</dt>", html=False)

    finding = Finding(
        finding_type="KATFindingType|KAT-MEDIUM-TLS-CIPHER",
        ooi="Network|testnetwork",
        description=cipher["description"],
        proof=cipher["proof"],
    )
    html = render_to_string("partials/finding_occurrence_definition_list.html", {"finding": finding})
    assert "Cipher B - current suite." in html
    assert "Cipher A - removed suite" not in html
