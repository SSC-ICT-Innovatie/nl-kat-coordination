import random

import pytest
from crisis_room.forms import AddFindingListDashboardItemForm, AddObjectListDashboardItemForm
from crisis_room.models import Dashboard, DashboardItem
from crisis_room.views import (
    AddDashboardView,
    CrisisRoomView,
    DashboardService,
    DeleteDashboardItemView,
    DeleteDashboardView,
    OrganizationsCrisisRoomView,
    UpdateDashboardItemView,
)
from django.core.exceptions import PermissionDenied
from django.http.request import QueryDict
from pytest_django.asserts import assertContains, assertNotContains

from tests.conftest import setup_request


def test_expected_findings_results_dashboard(rf, mocker, client_member, expected_findings_results):
    """Test if the view is visible and if data is shown in the tables."""

    dashboard_service = mocker.patch("crisis_room.views.DashboardService")()
    dashboard_service.get_dashboard_items.return_value = expected_findings_results

    summary = dashboard_service.get_organizations_findings_summary.side_effect = (
        DashboardService().get_organizations_findings_summary
    )
    summary_data = summary(expected_findings_results)

    total_finding_types = summary_data["total_finding_types"]
    total_occurrences = summary_data["total_occurrences"]

    org_code_a, org_name_a = (
        expected_findings_results[0].item.dashboard.organization.code,
        expected_findings_results[0].item.dashboard.organization.name,
    )
    org_code_b, org_name_b = (
        expected_findings_results[1].item.dashboard.organization.code,
        expected_findings_results[1].item.dashboard.organization.name,
    )

    request = setup_request(rf.get("crisis_room"), client_member.user)
    response = CrisisRoomView.as_view()(request)

    assert response.status_code == 200
    # View should show the 'Findings overview' for all organizations
    assertContains(response, "<h2>Findings overview</h2>", html=True)
    assertContains(response, '<caption class="visually-hidden">Total per severity overview</caption>', html=True)
    assertContains(
        response,
        '<tr><td><span class="critical">Critical</span></td><td class="number">1</td><td class="number">3</td></tr>',
        html=True,
    )
    assertContains(response, '<tr><td>Total</td><td class="number">16</td><td class="number">24</td></tr>', html=True)

    # View should also show the 'Findings for all orgniazations' table for all organizations
    assertContains(response, "<h2>Findings per organization</h2>", html=True)
    assertContains(response, '<caption class="visually-hidden">Findings per organization overview</caption>', html=True)

    assertContains(response, f'<td><a href="/en/crisis-room/{org_code_a}/">{org_name_a}</a></td>', html=True)
    assertContains(response, "<h5>Findings overview</h5>", html=True)
    assertContains(response, '<td>Total</td><td class="number">4</td><td class="number">7</td>', html=True)

    assertContains(response, f'<td><a href="/en/crisis-room/{org_code_b}/">{org_name_b}</a></td>', html=True)

    assertContains(
        response,
        f'<td>Total</td><td class="number">{total_finding_types}</td><td class="number">{total_occurrences}</td>',
        html=True,
    )
    assertContains(
        response, "<p>No critical and high findings have been identified for this organization.</p>", html=True
    )


def test_get_organizations_findings_summary(expected_findings_results):
    """Test if summary has counted the results of both reports correctly."""
    dashboard_service = DashboardService()
    summary_results = dashboard_service.get_organizations_findings_summary(expected_findings_results)

    assert summary_results["total_by_severity_per_finding_type"] == {
        "critical": 1,
        "high": 2,
        "medium": 7,
        "low": 3,
        "recommendation": 1,
        "pending": 1,
        "unknown": 1,
    }
    assert summary_results["total_by_severity"] == {
        "critical": 3,
        "high": 3,
        "medium": 9,
        "low": 6,
        "recommendation": 1,
        "pending": 1,
        "unknown": 1,
    }
    assert summary_results["total_finding_types"] == 16
    assert summary_results["total_occurrences"] == 24


def test_get_organizations_findings_summary_no_input():
    """Test if summary returns an empty dict if there is not input."""
    dashboard_service = DashboardService()
    summary_results = dashboard_service.get_organizations_findings_summary({})

    assert summary_results == {}


def test_get_organizations_findings(findings_reports_data):
    """Test if the highest risk level is collected, only critical and high finding types are returned."""
    dashboard_service = DashboardService()
    report_data = list(findings_reports_data.values())[0]

    report_data["findings"]["finding_types"] = [
        {"finding_type": {"risk_severity": "critical"}, "occurrences": {}},
        {"finding_type": {"risk_severity": "high"}, "occurrences": {}},
        {"finding_type": {"risk_severity": "low"}, "occurrences": {}},
    ]
    findings = dashboard_service.get_organizations_findings(report_data)

    assert len(findings["findings"]["finding_types"]) == 2
    assert findings["highest_risk_level"] == "critical"
    assert findings["findings"]["finding_types"][0]["finding_type"]["risk_severity"] == "critical"
    assert findings["findings"]["finding_types"][1]["finding_type"]["risk_severity"] == "high"


def test_get_organizations_findings_no_finding_types(findings_reports_data):
    """
    When there are no finding types, the result should contain the report data and
    highest_risk_level should be an empty string.
    """
    dashboard_service = DashboardService()
    report_data = list(findings_reports_data.values())[0]
    findings = dashboard_service.get_organizations_findings(report_data)

    assert findings == report_data | {"highest_risk_level": ""}


def test_get_organizations_findings_no_input():
    """When there is no input, the result should only contain an empty highest_risk_level"""
    dashboard_service = DashboardService()
    findings = dashboard_service.get_organizations_findings({})

    assert findings == {"highest_risk_level": ""}


def test_collect_findings_dashboard(findings_results, expected_findings_results):
    """
    Test if the right dashboard is filtered and if the method returns the right dict format.
    Only the most recent report should be visible in the dict.
    """

    assert len(findings_results) == len(expected_findings_results)

    for index in range(len(findings_results)):
        assert findings_results[index].item == expected_findings_results[index].item
        assert findings_results[index].data["report"] == expected_findings_results[index].data["report"]
        assert findings_results[index].data["report_data"] == expected_findings_results[index].data["report_data"]


def test_create_dashboard(rf, redteam_member):
    dashboard_name = "test"
    request = setup_request(
        rf.post("add_dashboard", {"organization_code": "test", "dashboard_name": dashboard_name}), redteam_member.user
    )
    response = AddDashboardView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302

    messages = list(request._messages)

    assert f"Dashboard '{dashboard_name}' has been created." in messages[0].message

    dashboard = Dashboard.objects.filter(name=dashboard_name)
    assert dashboard.exists()
    assert len(dashboard) == 1


def test_create_dashboard_no_permission(rf, client_member):
    dashboard_name = "test"
    request = setup_request(
        rf.post("add_dashboard", {"organization_code": "test", "dashboard_name": dashboard_name}), client_member.user
    )

    with pytest.raises(PermissionDenied):
        AddDashboardView.as_view()(request, organization_code=client_member.organization.code)


def test_create_dashboard_already_exist(rf, redteam_member):
    dashboard_name = "test"
    Dashboard.objects.create(name=dashboard_name, organization=redteam_member.organization)

    request = setup_request(
        rf.post("add_dashboard", {"organization_code": "test", "dashboard_name": dashboard_name}), redteam_member.user
    )
    response = AddDashboardView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302

    messages = list(request._messages)

    assert f"Dashboard with name '{dashboard_name}' already exists." in messages[0].message


def test_update_dashboard_item_positioning(rf, redteam_member, dashboard_items):
    item_1, item_2, item_3, item_4 = dashboard_items[0], dashboard_items[1], dashboard_items[2], dashboard_items[3]

    # save positions before swapping to check positions later
    position_item_1 = item_1.position
    position_item_2 = item_2.position
    position_item_3 = item_3.position
    position_item_4 = item_4.position

    request = setup_request(
        rf.post("update_dashboard_item", {"dashboard_item": item_3.id, "move": "up"}), redteam_member.user
    )
    response = UpdateDashboardItemView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302

    dashboard_data_item_1 = DashboardItem.objects.get(id=item_1.id, dashboard__organization=redteam_member.organization)
    dashboard_data_item_2 = DashboardItem.objects.get(id=item_2.id, dashboard__organization=redteam_member.organization)
    dashboard_data_item_3 = DashboardItem.objects.get(id=item_3.id, dashboard__organization=redteam_member.organization)
    dashboard_data_item_4 = DashboardItem.objects.get(id=item_4.id, dashboard__organization=redteam_member.organization)

    # item 1 must have moved down (+1), because we have changed item 2 to move up (-1)
    assert dashboard_data_item_2.position == position_item_2 + 1
    assert dashboard_data_item_3.position == position_item_3 - 1

    # last and first item position must not be changed
    assert dashboard_data_item_1.position == position_item_1
    assert dashboard_data_item_4.position == position_item_4


def test_update_dashboard_item_positioning_no_permission(rf, client_member, dashboard_items):
    request = setup_request(
        rf.post("update_dashboard_item", {"dashboard_item": dashboard_items[2].id, "move": "up"}), client_member.user
    )
    with pytest.raises(PermissionDenied):
        UpdateDashboardItemView.as_view()(request, organization_code=client_member.organization.code)


def test_update_dashboard_item_positioning_lower_than_first_item(rf, redteam_member, dashboard_items):
    item_1 = dashboard_items[0]
    position_item_1 = item_1.position

    request = setup_request(
        rf.post("update_dashboard_item", {"dashboard_item": item_1.id, "move": "up"}), redteam_member.user
    )
    response = UpdateDashboardItemView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302

    dashboard_data_item_1 = DashboardItem.objects.get(id=item_1.id, dashboard__organization=redteam_member.organization)

    # nothing will be updated, as we cannot move up if this is the first item
    assert dashboard_data_item_1.position == position_item_1


def test_update_dashboard_item_positioning_greater_than_last_item(rf, redteam_member, dashboard_items):
    item_4 = dashboard_items[3]
    position_item_4 = item_4.position

    request = setup_request(
        rf.post("update_dashboard_item", {"dashboard_item": item_4.id, "move": "down"}), redteam_member.user
    )
    response = UpdateDashboardItemView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302

    dashboard_data_item_4 = DashboardItem.objects.get(id=item_4.id, dashboard__organization=redteam_member.organization)

    # nothing will be updated, as we cannot move down if this is the last item
    assert dashboard_data_item_4.position == position_item_4


def test_delete_dashboard_item(rf, redteam_member, dashboard_items):
    item_1 = dashboard_items[0]
    item_2 = dashboard_items[1]
    item_3 = dashboard_items[2]
    item_4 = dashboard_items[3]

    position_item_1 = item_1.position
    position_item_2 = item_2.position
    position_item_4 = item_4.position

    request = setup_request(
        rf.post("delete_dashboard_item", {"dashboard_item_name": item_3.name, "dashboard_item_id": item_3.id}),
        redteam_member.user,
    )
    response = DeleteDashboardItemView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302

    dashboard_data_item_1 = DashboardItem.objects.get(id=item_1.id, dashboard__organization=redteam_member.organization)
    dashboard_data_item_2 = DashboardItem.objects.get(id=item_2.id, dashboard__organization=redteam_member.organization)

    with pytest.raises(DashboardItem.DoesNotExist):
        DashboardItem.objects.get(id=item_3.id, dashboard__organization=redteam_member.organization)

    dashboard_data_item_4 = DashboardItem.objects.get(id=item_4.id, dashboard__organization=redteam_member.organization)

    messages = list(request._messages)

    assert f"Dashboard item '{item_3.name}' has been deleted." in messages[0].message

    # check if other dashboard items repositioned based on the deleted item.

    assert dashboard_data_item_1.position == position_item_1
    assert dashboard_data_item_2.position == position_item_2

    assert dashboard_data_item_4.position == position_item_4 - 1


def test_delete_dashboard_item_no_permission(rf, client_member, dashboard_items):
    request = setup_request(
        rf.post(
            "delete_dashboard_item",
            {"dashboard_item_name": dashboard_items[2].name, "dashboard_item_id": dashboard_items[2].id},
        ),
        client_member.user,
    )
    with pytest.raises(PermissionDenied):
        DeleteDashboardItemView.as_view()(request, organization_code=client_member.organization.code)


def test_delete_dashboard_item_repositioning(rf, client_member, dashboard_items):
    """After repositioning of items, mixin the order, see when deleting if positioning calculates correctly"""

    positions = [dashboard_item.position for dashboard_item in dashboard_items]
    random.seed(999)
    random.shuffle(positions)

    # change the positions of dashboard items randomly
    for index, dashboard_item in enumerate(dashboard_items):
        dashboard_item.position = positions[index]
        dashboard_item.save()

    dashboard_items[1].delete()

    # get items after deleting, we order items by position
    dashboard_items = DashboardItem.objects.all().order_by("position")

    # position must match index of items
    for index, dashboard_item in enumerate(dashboard_items, start=1):
        assert dashboard_item.position == index


def test_delete_dashboard_item_no_dashboard(rf, redteam_member, dashboard_items):
    item_3 = dashboard_items[2]

    request = setup_request(
        rf.post("delete_dashboard_item", {"dashboard_item_name": item_3.name, "dashboard_item_id": 100}),
        redteam_member.user,
    )
    response = DeleteDashboardItemView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302

    # item still exists but dashboard with unknown name cannot be found
    DashboardItem.objects.get(id=item_3.id, dashboard__organization=redteam_member.organization)

    messages = list(request._messages)

    assert f"Dashboard item '{item_3.name}' not found." in messages[0].message


def test_delete_dashboard_item_no_dashboard_data(rf, redteam_member, dashboard_items):
    item_2 = dashboard_items[1]

    request = setup_request(
        rf.post("delete_dashboard_item", {"dashboard_item_name": "bla", "dashboard_item_id": item_2.id}),
        redteam_member.user,
    )
    response = DeleteDashboardItemView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302

    DashboardItem.objects.get(id=item_2.id, dashboard__organization=redteam_member.organization)

    messages = list(request._messages)

    assert "Dashboard item 'bla' not found." in messages[0].message


def test_delete_dashboard(rf, redteam_member, dashboard_items):
    dashboard_name = dashboard_items[1].dashboard.name
    dashboard_id = dashboard_items[1].dashboard.id

    request = setup_request(
        rf.post("delete_dashboard", {"dashboard_id": dashboard_id, "dashboard_name": dashboard_name}),
        redteam_member.user,
    )
    response = DeleteDashboardView.as_view()(request, organization_code=redteam_member.organization.code)

    assert response.status_code == 302

    messages = list(request._messages)

    assert f"Dashboard '{dashboard_name}' has been deleted." in messages[0].message

    with pytest.raises(Dashboard.DoesNotExist):
        Dashboard.objects.get(id=dashboard_id)


def test_delete_dashboard_no_permission(rf, client_member, dashboard_items):
    item_2 = dashboard_items[1]

    dashboard_name = item_2.dashboard.name

    request = setup_request(rf.post("delete_dashboard", {"dashboard": dashboard_name}), client_member.user)
    with pytest.raises(PermissionDenied):
        DeleteDashboardView.as_view()(request, organization_code=client_member.organization.code)


def test_create_dashboard_item_form_object_list(client_member, dashboard_items):
    qdict = QueryDict(mutable=True)
    qdict.update(
        {
            "dashboard": dashboard_items[0].dashboard.id,
            "title": "Test Form",
            "order_by": "object_type-asc",
            "limit": "10",
            "size": "2",
            "observed_at": "2025-05-07",
            "ooi_type": "Hostname",
            "search_string": "",
            "template": "partials/dashboard_ooi_list.html",
            "recipe_id": "",
            "source": "object_list",
        }
    )

    qdict.setlist("columns", ["object", "object_type"])

    form = AddObjectListDashboardItemForm(organization=client_member.organization, data=qdict)

    assert form.is_valid()

    # Check if dashboard data is created, after form is valid, should be created at this point
    DashboardItem.objects.get(dashboard=dashboard_items[0].dashboard, name="Test Form")

    # test empty data
    form = AddObjectListDashboardItemForm(organization=client_member.organization, data=QueryDict(""))

    assert not form.is_valid()

    fields = list(form.errors)

    # errors on all fields
    assert "dashboard" in fields
    assert "title" in fields
    assert "order_by" in fields
    assert "limit" in fields
    assert "size" in fields

    # change for data to have the same title that already exists
    qdict["title"] = dashboard_items[0].name

    form = AddObjectListDashboardItemForm(organization=client_member.organization, data=qdict)
    assert not form.is_valid()

    fields = list(form.errors)
    errors = list(form.errors.values())

    assert "title" in fields

    # duplicate title throws form error
    for error_list in errors:
        assert (
            "An item with that name already exists. Try a different title." in error_list
            or "An error occurred while adding dashboard item." in error_list
        )

    # set it back
    qdict["title"] = "Test Form"

    # None existent dashboard
    qdict["dashboard"] = ""

    form = AddObjectListDashboardItemForm(organization=client_member.organization, data=qdict)
    assert not form.is_valid()

    fields = list(form.errors)
    errors = list(form.errors.values())

    assert "dashboard" in fields

    for error_list in errors:
        assert "This field is required." in error_list or "Dashboard does not exist." in error_list


def test_organization_crisis_room(rf, mocker, client_member, dashboard_items):
    mocker.patch("crisis_room.views.OctopoesAPIConnector")

    request = setup_request(rf.get("organization_crisis_room"), client_member.user)
    response = OrganizationsCrisisRoomView.as_view()(
        request, organization_code=client_member.organization.code, id=dashboard_items[0].dashboard.id
    )

    assert response.status_code == 200

    for dashboard_item in dashboard_items:
        assertContains(response, dashboard_item.name)

    assertContains(response, dashboard_items[0].dashboard.name)
    assertContains(response, "Object list")


def test_clients_permissions_for_dashboard(rf, mocker, client_member, dashboard_items):
    mocker.patch("crisis_room.views.OctopoesAPIConnector")

    request = setup_request(rf.get("organization_crisis_room"), client_member.user)
    response = OrganizationsCrisisRoomView.as_view()(
        request, organization_code=client_member.organization.code, id=dashboard_items[0].dashboard.id
    )

    assert response.status_code == 200

    assert not client_member.can_modify_dashboard
    assert not client_member.can_modify_dashboard_item

    # Clients are restricted to see Delete or add buttons
    assertNotContains(response, "+ Add Dashboard")
    assertNotContains(response, "Delete Dashboard")
    assertNotContains(response, "Delete item ")


def test_create_dashboard_item_form_findings_list(client_member, dashboard_items_from_findings_list):
    qdict = QueryDict(mutable=True)
    qdict.update(
        {
            "dashboard": dashboard_items_from_findings_list[0].dashboard.id,
            "title": "Test Form",
            "order_by": "score-asc",
            "limit": "10",
            "size": "2",
            "observed_at": "2025-05-07",
            "muted_findings": "non-muted",
            "source": "finding_list",
            "template": "partials/dashboard_finding_list.html",
        }
    )

    qdict.setlist("columns", ["severity", "finding"])

    form = AddFindingListDashboardItemForm(organization=client_member.organization, data=qdict)

    assert form.is_valid()

    # Check if dashboard data is created, after form is valid, should be created at this point
    DashboardItem.objects.get(dashboard=dashboard_items_from_findings_list[0].dashboard, name="Test Form")

    # test empty data
    form = AddFindingListDashboardItemForm(organization=client_member.organization, data=QueryDict(""))

    assert not form.is_valid()

    fields = list(form.errors)

    # errors on all fields
    assert "dashboard" in fields
    assert "title" in fields
    assert "order_by" in fields
    assert "limit" in fields
    assert "size" in fields

    # change for data to have the same title that already exists
    qdict["title"] = dashboard_items_from_findings_list[0].name

    form = AddFindingListDashboardItemForm(organization=client_member.organization, data=qdict)

    assert not form.is_valid()

    fields = list(form.errors)
    errors = list(form.errors.values())

    assert "title" in fields

    # duplicate title throws form error
    for error_list in errors:
        assert (
            "An item with that name already exists. Try a different title." in error_list
            or "An error occurred while adding dashboard item." in error_list
        )

    # set it back
    qdict["title"] = "Test Form"

    # None existent dashboard
    qdict["dashboard"] = ""

    form = AddFindingListDashboardItemForm(organization=client_member.organization, data=qdict)
    assert not form.is_valid()

    fields = list(form.errors)
    errors = list(form.errors.values())

    assert "dashboard" in fields

    for error_list in errors:
        assert "This field is required." in error_list or "Dashboard does not exist." in error_list
