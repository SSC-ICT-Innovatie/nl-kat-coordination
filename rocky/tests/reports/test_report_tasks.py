from pytest_django.asserts import assertContains

from rocky.scheduler import SchedulerConnectError, SchedulerValidationError
from rocky.views.tasks import ReportsTaskListView
from tests.conftest import setup_request


def test_report_task_list(rf, client_member, mock_scheduler, reports_task_list):
    """
    Test report task general page .
    """

    mock_scheduler.list_tasks.return_value = reports_task_list

    recipe_ids = [report_task.data.report_recipe_id for report_task in reports_task_list.results]

    response = ReportsTaskListView.as_view()(
        setup_request(rf.get("reports_task_list"), client_member.user),
        organization_code=client_member.organization.code,
    )

    assert response.status_code == 200

    assertContains(response, "List of tasks for reports")
    assertContains(response, '<td><i class="icon failed"></i>Failed</td>', html=True)
    assertContains(response, '<td><i class="icon completed"></i>Completed</td>', html=True)
    assertContains(response, recipe_ids[0])
    assertContains(response, recipe_ids[1])


def test_report_task_list_connect_error(rf, client_member, mock_scheduler):
    """
    Test report task general page .
    """

    mock_scheduler.list_tasks.side_effect = SchedulerConnectError

    request = setup_request(rf.get("reports_task_list"), client_member.user)

    response = ReportsTaskListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assert list(request._messages)[0].message == "Could not connect to Scheduler. Service is possibly down."


def test_report_task_list_validation_error(rf, client_member, mock_scheduler):
    """
    Test report task general page .
    """

    mock_scheduler.list_tasks.side_effect = SchedulerValidationError

    request = setup_request(rf.get("reports_task_list"), client_member.user)

    response = ReportsTaskListView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assert list(request._messages)[0].message == "Your request could not be validated."
