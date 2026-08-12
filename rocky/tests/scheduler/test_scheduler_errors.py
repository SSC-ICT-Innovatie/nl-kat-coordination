import pytest
from django.http import Http404

from rocky.scheduler import (
    SchedulerConnectError,
    SchedulerTaskNotFound,
    SchedulerTooManyRequestError,
    SchedulerValidationError,
)
from rocky.views.task_detail import NormalizerTaskJSONView
from rocky.views.tasks import BoefjesTaskListView
from tests.conftest import setup_request


def test_tasks_view_connect_error(rf, client_member, mock_scheduler):
    mock_scheduler.list_tasks.side_effect = SchedulerConnectError

    request = setup_request(rf.get("boefjes_task_list"), client_member.user)
    response = BoefjesTaskListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200

    assert list(request._messages)[0].message == "Could not connect to Scheduler. Service is possibly down."


def test_tasks_view_validation_error(rf, client_member, mock_scheduler):
    mock_scheduler.list_tasks.side_effect = SchedulerValidationError

    request = setup_request(rf.get("boefjes_task_list"), client_member.user)
    response = BoefjesTaskListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200

    assert list(request._messages)[0].message == "Your request could not be validated."


def test_tasks_view_too_many_requests_error(rf, client_member, mock_scheduler):
    mock_scheduler.list_tasks.side_effect = SchedulerTooManyRequestError

    request = setup_request(rf.get("boefjes_task_list"), client_member.user)
    response = BoefjesTaskListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200

    assert (
        list(request._messages)[0].message
        == "Scheduler is receiving too many requests. Increase SCHEDULER_PQ_MAXSIZE or wait for task to finish."
    )


def test_get_task_details_json_bad_task_id(rf, client_member, mock_scheduler):
    mock_scheduler.get_task_details.side_effect = SchedulerTaskNotFound
    request = setup_request(rf.get("normalizer_task_view"), client_member.user)

    with pytest.raises(Http404):
        NormalizerTaskJSONView.as_view()(request, organization_code=client_member.organization.code, task_id="/delete")


def test_reschedule_task_bad_task_id(rf, client_member, mock_bytes_client, mock_scheduler):
    mock_scheduler.get_task_details.side_effect = SchedulerTaskNotFound

    request = setup_request(
        rf.post("task_list", {"action": "reschedule_task", "task_id": "/delete"}), client_member.user
    )

    with pytest.raises(Http404):
        BoefjesTaskListView.as_view()(request, organization_code=client_member.organization.code)
