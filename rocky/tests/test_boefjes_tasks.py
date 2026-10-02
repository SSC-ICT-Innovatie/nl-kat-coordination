import json
import zipfile

import pytest
from django.http import Http404
from django.utils.translation import override
from katalogus.client import Boefje
from pytest_django.asserts import assertContains, assertNotContains
from tools.enums import SCAN_LEVEL

from rocky.scheduler import SchedulerTooManyRequestError
from rocky.views.bytes_raw import BytesRawView
from rocky.views.tasks import BoefjesTaskListView
from tests.conftest import setup_request


def test_boefjes_tasks(rf, client_member, mock_scheduler):
    request = setup_request(rf.get("boefjes_task_list"), client_member.user)
    response = BoefjesTaskListView.as_view()(
        request,
        organization_code=client_member.organization.code,
        scheduler_id="boefje-test",
        task_type="boefje",
        status=None,
        min_created_at=None,
        max_created_at=None,
        input_ooi=None,
    )

    assert response.status_code == 200


def test_tasks_view_simple(rf, client_member, mock_scheduler, mock_scheduler_client_task_list):
    request = setup_request(rf.get("boefjes_task_list"), client_member.user)
    response = BoefjesTaskListView.as_view()(request, organization_code=client_member.organization.code)

    assertContains(response, "Completed")


def test_tasks_view_status_translated(rf, client_member, mock_scheduler, mock_scheduler_client_task_list):
    """#4234: the status label in the task list rows must follow the active language,
    matching the status filter dropdown (which is translated via ChoiceField labels)."""
    with override("nl"):
        request = setup_request(rf.get("boefjes_task_list"), client_member.user)
        response = BoefjesTaskListView.as_view()(request, organization_code=client_member.organization.code)
        assertContains(response, "Voltooid")
        assertNotContains(response, ">Completed<")


def test_reschedule_task(rf, client_member, mock_scheduler, task):
    mock_scheduler.get_task_details.return_value = task
    request = setup_request(
        rf.post(
            f"/en/{client_member.organization.code}/tasks/boefjes/?task_id={task.id}",
            data={"action": "reschedule_task"},
        ),
        client_member.user,
    )
    response = BoefjesTaskListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assert list(request._messages)[0].message == (
        "Your task is scheduled and will soon be started in the background. "
        "Results will be added to the object list when they are in. "
        "It may take some time, a refresh of the page may be needed to show the results."
    )


def test_reschedule_task_already_queued(rf, client_member, mock_scheduler, mocker, task):
    mock_scheduler.get_task_details.return_value = task
    mock_scheduler.push_task.side_effect = SchedulerTooManyRequestError

    request = setup_request(
        rf.post(
            f"/en/{client_member.organization.code}/tasks/boefjes/?task_id={task.id}",
            data={"action": "reschedule_task"},
        ),
        client_member.user,
    )

    response = BoefjesTaskListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assert (
        list(request._messages)[0].message
        == "Scheduler is receiving too many requests. Increase SCHEDULER_PQ_MAXSIZE or wait for task to finish."
    )


def test_reschedule_task_from_other_org(rf, client_member, client_member_b, mock_scheduler, task):
    mock_scheduler.get_task_details.return_value = task

    request = setup_request(
        rf.post(
            f"/en/{client_member.organization.code}/tasks/boefjes/?task_id={task.id}",
            data={"action": "reschedule_task"},
        ),
        client_member_b.user,
    )
    with pytest.raises(Http404):
        BoefjesTaskListView.as_view()(request, organization_code=client_member.organization.code)


def test_download_task_other_org_from_other_org_url(
    rf, client_member, client_member_b, mock_bytes_client, bytes_raw_metas
):
    with pytest.raises(Http404):
        BytesRawView.as_view()(
            setup_request(rf.get("bytes_raw"), client_member.user),
            organization_code=client_member_b.organization.code,
            boefje_meta_id=bytes_raw_metas[0]["id"],
        )


def test_download_task_same_org(rf, client_member, mock_bytes_client, bytes_raw_metas, bytes_get_raw):
    mock_bytes_client().get_raw.return_value = bytes_get_raw
    mock_bytes_client().get_raw_metas.return_value = bytes_raw_metas

    request = setup_request(rf.get("bytes_raw"), client_member.user)

    response = BytesRawView.as_view()(
        request, organization_code=client_member.organization.code, boefje_meta_id=bytes_raw_metas[0]["id"]
    )

    assert response.status_code == 200


def test_download_task_no_raw(rf, client_member, mock_bytes_client, bytes_raw_metas):
    mock_bytes_client().get_raw_metas.return_value = []

    request = setup_request(rf.get("bytes_raw"), client_member.user)

    response = BytesRawView.as_view()(
        request, organization_code=client_member.organization.code, boefje_meta_id=bytes_raw_metas[0]["id"]
    )

    assert response.status_code == 302
    assert list(request._messages)[0].message == "The task does not have any raw data."


def test_download_task_strips_environment_secrets(
    rf, client_member, mock_bytes_client, mock_mixins_katalogus, bytes_raw_metas, bytes_get_raw
):
    """#4508: only secret-marked fields are stripped from the boefje environment,
    not the entire environment. Non-secret fields remain visible."""
    mock_bytes_client().get_raw.return_value = bytes_get_raw
    mock_bytes_client().get_raw_metas.return_value = bytes_raw_metas
    mock_mixins_katalogus.get_plugin.return_value = Boefje(
        id="dns-sec",
        name="dns-sec",
        type="boefje",
        enabled=True,
        scan_level=SCAN_LEVEL.L0,
        boefje_schema={
            "type": "object",
            "properties": {"SECRET_TOKEN": {"type": "string"}, "NON_SECRET": {"type": "string"}},
            "secret": ["SECRET_TOKEN"],
        },
    )

    request = setup_request(rf.get("bytes_raw"), client_member.user)

    response = BytesRawView.as_view()(
        request, organization_code=client_member.organization.code, boefje_meta_id=bytes_raw_metas[0]["id"]
    )

    assert response.status_code == 200
    with zipfile.ZipFile(response.file_to_stream) as zf:
        meta_files = [n for n in zf.namelist() if n.startswith("raw_meta_")]
        for meta_file in meta_files:
            meta = json.loads(zf.read(meta_file))
            env = meta["boefje_meta"]["environment"]
            assert "SECRET_TOKEN" not in env
            assert env["NON_SECRET"] == "visible"
