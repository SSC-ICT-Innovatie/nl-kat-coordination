from urllib.parse import urlencode

import pytest
from katalogus.client import Boefje
from pytest_django.asserts import assertContains, assertNotContains
from tools.enums import SCAN_LEVEL
from tools.models import Indemnification

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
            "ooi": "Question|/test|Network|testnetwork",
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

    response = OOIDetailView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assert mock_organization_view_octopoes().get_tree.call_count == 1

    assertContains(response, "Question")
    assertContains(response, "Fill out this form to answer the Question (again)")
    assertContains(response, "Submit")


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
