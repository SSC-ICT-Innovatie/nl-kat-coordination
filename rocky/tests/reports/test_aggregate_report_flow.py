import json

from pytest_django.asserts import assertContains
from reports.views.aggregate_report import (
    OOISelectionAggregateReportView,
    ReportTypesSelectionAggregateReportView,
    SaveAggregateReportView,
    SetupScanAggregateReportView,
)
from reports.views.base import ViewReportView

from octopoes.models.pagination import Paginated
from octopoes.models.types import OOIType
from tests.conftest import get_aggregate_report_data, setup_request


def test_select_all_oois_post_to_select_report_types(
    rf, client_member, valid_time, mock_organization_view_octopoes, listed_hostnames
):
    """
    Will send the selected oois to the report type selection page.
    """

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](
        count=len(listed_hostnames), items=listed_hostnames
    )

    request = setup_request(
        rf.post(
            "aggregate_report_select_report_types",
            {"observed_at": valid_time.strftime("%Y-%m-%d"), "ooi": listed_hostnames},
        ),
        client_member.user,
    )

    response = ReportTypesSelectionAggregateReportView.as_view()(
        request, organization_code=client_member.organization.code
    )

    assert response.status_code == 200
    total_objects = str(len(listed_hostnames))
    assertContains(response, f"You have selected {total_objects} objects in the previous step.")


def test_select_some_oois_post_to_select_report_types(
    rf, client_member, valid_time, mock_organization_view_octopoes, listed_hostnames
):
    """
    Will send the selected oois to the report type selection page.
    """

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](
        count=len(listed_hostnames), items=listed_hostnames
    )

    ooi_pks = [hostname.primary_key for hostname in listed_hostnames]
    selection = ooi_pks[0:2]

    request = setup_request(
        rf.post(
            "aggregate_report_select_report_types", {"observed_at": valid_time.strftime("%Y-%m-%d"), "ooi": selection}
        ),
        client_member.user,
    )

    response = ReportTypesSelectionAggregateReportView.as_view()(
        request, organization_code=client_member.organization.code
    )

    assert response.status_code == 200

    total_objects = str(len(selection))

    assertContains(response, f"You have selected {total_objects} objects in the previous step.")


def test_select_query_post_to_select_report_types(
    rf, client_member, valid_time, mock_organization_view_octopoes, listed_hostnames
):
    """
    Will send the query to the report type selection page.
    """

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](
        count=len(listed_hostnames), items=listed_hostnames
    )

    request = setup_request(
        rf.post(
            "aggregate_report_select_report_types",
            {"observed_at": valid_time.strftime("%Y-%m-%d"), "object_selection": "query"},
        ),
        client_member.user,
    )

    response = ReportTypesSelectionAggregateReportView.as_view()(
        request, organization_code=client_member.organization.code
    )

    assert response.status_code == 200
    assert response.context_data["selected_oois"] == []

    assertContains(response, "You have selected a live set in the previous step.")
    assertContains(response, "this live set results in 0 objects.")


def test_change_ooi_selection_for_none_selection(
    rf, client_member, valid_time, mock_organization_view_octopoes, listed_hostnames
):
    """
    Will send the selected oois to the report type selection page.
    """

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](
        count=len(listed_hostnames), items=listed_hostnames
    )

    request = setup_request(
        rf.post("aggregate_report_select_oois", {"observed_at": valid_time.strftime("%Y-%m-%d")}), client_member.user
    )

    response = OOISelectionAggregateReportView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assert response.context_data["selected_oois"] == []
    assert list(request._messages)[0].message == "Select at least one OOI to proceed."


def test_change_ooi_selection_with_ooi_selection(
    rf, client_member, valid_time, mock_organization_view_octopoes, listed_hostnames
):
    """
    Will send the selected oois to the report type selection page.
    """

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](
        count=len(listed_hostnames), items=listed_hostnames
    )

    ooi_pks = [hostname.primary_key for hostname in listed_hostnames]
    selection = ooi_pks[0:2]

    request = setup_request(
        rf.post("aggregate_report_select_oois", {"observed_at": valid_time.strftime("%Y-%m-%d"), "ooi": selection}),
        client_member.user,
    )

    response = OOISelectionAggregateReportView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200

    oois_fetched_from_post = response.context_data["selected_oois"]

    assert len(oois_fetched_from_post) == 2


def test_report_types_selection_nothing_selected(
    rf, client_member, valid_time, mock_organization_view_octopoes, mock_katalogus_client, listed_hostnames
):
    """
    Will send the selected report types to the configuration page (set plugins).
    """

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](
        count=len(listed_hostnames), items=listed_hostnames
    )

    request = setup_request(
        rf.post("aggregate_report_setup_scan", {"observed_at": valid_time.strftime("%Y-%m-%d")}), client_member.user
    )

    response = SetupScanAggregateReportView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 307
    assert list(request._messages)[0].message == "Select at least one report type to proceed."


def test_report_types_selection(
    rf,
    client_member,
    valid_time,
    mock_organization_view_octopoes,
    listed_hostnames,
    mocker,
    boefje_dns_records,
    boefje_nmap_tcp,
    rocky_health,
    mock_bytes_client,
):
    """
    Will send the selected report types to the configuration page (set plugins).
    """

    katalogus_mocker = mocker.patch("account.mixins.OrganizationView.katalogus_client")
    katalogus_mocker.get_plugins.return_value = [boefje_dns_records, boefje_nmap_tcp]

    rocky_health_mocker = mocker.patch("reports.report_types.aggregate_organisation_report.report.get_rocky_health")()
    rocky_health_mocker.return_value = rocky_health

    mock_bytes_client().upload_raw.return_value = "Report|e821aaeb-a6bd-427f-b064-e46837911a5d"

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](
        count=len(listed_hostnames), items=listed_hostnames
    )

    request = setup_request(
        rf.post(
            "aggregate_report_setup_scan",
            {"observed_at": valid_time.strftime("%Y-%m-%d"), "report_type": ["dns-report", "systems-report"]},
        ),
        client_member.user,
    )

    response = SetupScanAggregateReportView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 307  # if all plugins are enabled the view will auto redirect to generate report

    # Redirect to export setup
    assert response.headers["Location"] == "/en/test/reports/aggregate-report/export-setup/?"


def test_save_aggregate_report_view(
    rf,
    client_member,
    valid_time,
    mock_organization_view_octopoes,
    listed_hostnames,
    rocky_health,
    mocker,
    boefje_dns_records,
    mock_bytes_client,
):
    """
    Will send data through post to aggregate report and immediately creates a report (not scheduled).
    """

    katalogus_mocker = mocker.patch("account.mixins.OrganizationView.katalogus_client")
    katalogus_mocker.get_plugins.return_value = [boefje_dns_records]

    rocky_health_mocker = mocker.patch("reports.report_types.aggregate_organisation_report.report.get_rocky_health")()
    rocky_health_mocker.return_value = rocky_health

    mock_bytes_client().upload_raw.return_value = "Report|e821aaeb-a6bd-427f-b064-e46837911a5d"

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](
        count=len(listed_hostnames), items=listed_hostnames
    )

    request = setup_request(
        rf.post(
            "aggregate_report_save",
            {
                "observed_at": valid_time.strftime("%Y-%m-%d"),
                "ooi": listed_hostnames,
                "report_type": ["systems-report", "dns-report"],
                "start_date": "2024-01-01",
                "start_time": "10:10",
                "recurrence": "once",
                "parent_report_name_format": "${report_type} for ${oois_count} objects",
            },
        ),
        client_member.user,
    )

    response = SaveAggregateReportView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 302  # after post follows redirect, this to first create report ID
    assert "/reports/scheduled-reports/" in response.url


def test_save_aggregate_report_view_scheduled(
    rf,
    client_member,
    valid_time,
    mock_organization_view_octopoes,
    listed_hostnames,
    rocky_health,
    mocker,
    boefje_dns_records,
    mock_bytes_client,
):
    """
    Will send data through post to aggregate report and creates a scheduled aggregate report.
    """

    katalogus_mocker = mocker.patch("account.mixins.OrganizationView.katalogus_client")
    katalogus_mocker.get_plugins.return_value = [boefje_dns_records]

    rocky_health_mocker = mocker.patch("reports.report_types.aggregate_organisation_report.report.get_rocky_health")()
    rocky_health_mocker.return_value = rocky_health

    mock_bytes_client().upload_raw.return_value = "Report|1730b72f-b115-412e-ad44-dae6ab3edff9"

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](
        count=len(listed_hostnames), items=listed_hostnames
    )

    request = setup_request(
        rf.post(
            "aggregate_report_save",
            {
                "observed_at": valid_time.strftime("%Y-%m-%d"),
                "ooi": listed_hostnames,
                "report_type": ["systems-report", "vulnerability-report"],
                "start_date": "2024-01-01",
                "start_time": "10:10",
                "recurrence": "once",
                "parent_report_name_format": "${report_type} for ${oois_count} object(s)",
            },
        ),
        client_member.user,
    )

    response = SaveAggregateReportView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 302  # after post follows redirect, this to first create report ID
    assert response.url == f"/en/{client_member.organization.code}/reports/scheduled-reports/"


def test_json_download_aggregate_report(
    rf,
    client_member,
    get_aggregate_report_ooi,
    get_aggregate_report_from_bytes,
    mock_organization_view_octopoes,
    mock_bytes_client,
    mock_katalogus_client,
):
    mock_organization_view_octopoes().get_report.return_value = get_aggregate_report_ooi
    mock_bytes_client().get_raws.return_value = [
        ("7b305f0d-c0a7-4ad5-af1e-31f81fc229c2", get_aggregate_report_from_bytes)
    ]

    request = setup_request(
        rf.get("view_report_json", {"json": "true", "report_id": f"{get_aggregate_report_ooi.primary_key}"}),
        client_member.user,
    )

    json_response = ViewReportView.as_view()(request, organization_code=client_member.organization.code)

    assert json_response.status_code == 200

    json_response_data = json.dumps(json.loads(json_response.content))
    json_compare_data = json.dumps(get_aggregate_report_data())

    assert json_response_data == json_compare_data
