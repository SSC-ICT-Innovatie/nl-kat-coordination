from reports.views.report_overview import ScheduledReportsEnableDisableView, ScheduledReportsView

from octopoes.models.exception import ObjectNotFoundException
from rocky.scheduler import PaginatedSchedulesResponse, SchedulerError
from tests.conftest import setup_request


def test_delete_schedule(
    rf, redteam_member, mock_organization_view_octopoes, mock_scheduler, scheduled_report_recipe, scheduled_reports_list
):
    mock_scheduler.get_schedule_details.return_value = scheduled_reports_list[0]
    mock_scheduler.get_scheduled_reports.return_value = scheduled_reports_list
    mock_organization_view_octopoes().get.return_value = scheduled_report_recipe

    recipe_id = "ReportRecipe|" + scheduled_reports_list[0].data["report_recipe_id"]

    request = setup_request(rf.post("scheduled_reports", {"recipe_id": recipe_id}), redteam_member.user)

    response = ScheduledReportsView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert list(request._messages)[0].message == f"Recipe '{recipe_id}' deleted successfully"


def test_delete_schedule_no_recipe(
    rf, redteam_member, mock_organization_view_octopoes, mock_scheduler, scheduled_report_recipe, scheduled_reports_list
):
    mock_scheduler.get_scheduled_reports.return_value = scheduled_reports_list
    mock_organization_view_octopoes().get.return_value = scheduled_report_recipe

    request = setup_request(rf.post("scheduled_reports", {}), redteam_member.user)
    response = ScheduledReportsView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert list(request._messages)[0].message == "No schedule or recipe selected"


def test_delete_schedule_object_not_found(
    rf, redteam_member, mock_organization_view_octopoes, mock_scheduler, scheduled_report_recipe, scheduled_reports_list
):
    mock_scheduler.get_scheduled_reports.side_effect = scheduled_reports_list
    mock_organization_view_octopoes().get.return_value = scheduled_report_recipe
    mock_organization_view_octopoes().delete.side_effect = ObjectNotFoundException("Not found")

    request = setup_request(rf.post("scheduled_reports", {"recipe_id": "ReportRecipe|recipeNone"}), redteam_member.user)

    response = ScheduledReportsView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert list(request._messages)[0].message == "Recipe not found."


def test_delete_schedule_schedule_not_found(
    rf, redteam_member, mock_organization_view_octopoes, mock_scheduler, scheduled_report_recipe, scheduled_reports_list
):
    mock_scheduler.get_scheduled_reports.side_effect = scheduled_reports_list
    mock_organization_view_octopoes().get.return_value = scheduled_report_recipe
    mock_scheduler.delete_schedule.side_effect = SchedulerError

    request = setup_request(rf.post("scheduled_reports", {"recipe_id": "ReportRecipe|recipeNone"}), redteam_member.user)

    response = ScheduledReportsView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302
    assert (
        list(request._messages)[0].message
        == "The Scheduler has an unexpected error. Check the Scheduler logs for further details."
    )


def test_disable_schedule_message(rf, superuser_member, mock_scheduler, scheduled_reports_list):
    """Disabling an enabled schedule shows the 'disabled successfully' message."""
    mock_scheduler.post_schedule_search.return_value = PaginatedSchedulesResponse(
        count=1, results=scheduled_reports_list
    )

    recipe_id = scheduled_reports_list[0].data["report_recipe_id"]
    request = setup_request(
        rf.post("enable_disable_scheduled_reports", {"recipe_id": recipe_id, "report_name_format": "Test Report"}),
        superuser_member.user,
    )

    response = ScheduledReportsEnableDisableView.as_view()(
        request, organization_code=superuser_member.organization.code
    )

    assert response.status_code == 302
    messages = list(request._messages)
    assert len(messages) == 1
    assert "disabled successfully" in messages[0].message
    assert "enabled successfully" not in messages[0].message


def test_enable_schedule_message(rf, superuser_member, mock_scheduler, scheduled_reports_list):
    """Enabling a disabled schedule shows the 'enabled successfully' message."""
    disabled_schedule = scheduled_reports_list[0].model_copy(update={"enabled": False})
    mock_scheduler.post_schedule_search.return_value = PaginatedSchedulesResponse(count=1, results=[disabled_schedule])

    recipe_id = scheduled_reports_list[0].data["report_recipe_id"]
    request = setup_request(
        rf.post("enable_disable_scheduled_reports", {"recipe_id": recipe_id, "report_name_format": "Test Report"}),
        superuser_member.user,
    )

    response = ScheduledReportsEnableDisableView.as_view()(
        request, organization_code=superuser_member.organization.code
    )

    assert response.status_code == 302
    messages = list(request._messages)
    assert len(messages) == 1
    assert "enabled successfully" in messages[0].message
    assert "disabled successfully" not in messages[0].message


def test_enable_disable_schedule_scheduler_error(rf, superuser_member, mock_scheduler, scheduled_reports_list):
    """A SchedulerError when patching the schedule is shown as a message, not a 500."""
    mock_scheduler.post_schedule_search.return_value = PaginatedSchedulesResponse(
        count=1, results=scheduled_reports_list
    )
    mock_scheduler.patch_schedule.side_effect = SchedulerError

    recipe_id = scheduled_reports_list[0].data["report_recipe_id"]
    request = setup_request(
        rf.post("enable_disable_scheduled_reports", {"recipe_id": recipe_id, "report_name_format": "Test Report"}),
        superuser_member.user,
    )

    response = ScheduledReportsEnableDisableView.as_view()(
        request, organization_code=superuser_member.organization.code
    )

    assert response.status_code == 302
    assert (
        list(request._messages)[0].message
        == "The Scheduler has an unexpected error. Check the Scheduler logs for further details."
    )
