import pytest
from django.urls import resolve, reverse
from pytest_django.asserts import assertContains, assertNotContains
from reports.views.report_overview import ReportHistoryView, SubreportView

from octopoes.models.ooi.reports import HydratedReport
from octopoes.models.pagination import Paginated
from tests.conftest import setup_request


def test_report_history_less_than_five_subreports_two_input_objects(
    rf, client_member, mock_organization_view_octopoes, mocker, report_list_two_asset_reports
):
    """
    Test with less than 5 subreports and two input objects. Should contain:
    - Number of input objects
    - Chevron down button
    - Only 5 subreports should be shown
    - No "View all subreports" button
    """

    mocker.patch("account.mixins.OrganizationView.get_katalogus")
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("report_history", kwargs=kwargs)

    request = rf.get(url)
    request.resolver_match = resolve(url)

    setup_request(request, client_member.user)

    mock_organization_view_octopoes().list_reports.return_value = Paginated[HydratedReport](
        count=len(report_list_two_asset_reports), items=report_list_two_asset_reports
    )

    response = ReportHistoryView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200

    # Check table rows
    parent_report = report_list_two_asset_reports[0]
    assertContains(response, parent_report.name)
    assertContains(response, "<td>2</td>", html=True)
    assertContains(response, "Close asset report object details")

    # Check subreports, show only 5
    total_subreports = str(len(report_list_two_asset_reports[0].input_oois))
    child_report_1 = report_list_two_asset_reports[0].input_oois[0]
    child_report_2 = report_list_two_asset_reports[0].input_oois[1]
    assertContains(response, f"{total_subreports}/{total_subreports}")
    assertContains(
        response,
        f"This report consists of {total_subreports} asset reports with the following report types and objects:",
    )
    assertNotContains(
        response,
        (
            '<a href="/en/test/reports/report-history/subreports?'
            f'report_id={parent_report}" class="button">View all asset reports</a>'
        ),
        html=True,
    )
    assertContains(response, child_report_1)
    assertContains(response, child_report_2)

    # Check if all report types are shown
    assertContains(response, "Web System Report")


def test_report_history_more_than_five_asset_reports_one_input_object(
    rf, client_member, mock_organization_view_octopoes, mocker, report_list_six_asset_reports
):
    """
    Test with more than 5 subreports and one input object. Should contain:
    - Url of input item
    - Chevron down button
    - Only 5 subreports should be shown
    - "View all subreports" button

    """
    mocker.patch("account.mixins.OrganizationView.get_katalogus")
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("report_history", kwargs=kwargs)

    request = rf.get(url)
    request.resolver_match = resolve(url)

    setup_request(request, client_member.user)

    mock_organization_view_octopoes().list_reports.return_value = Paginated[HydratedReport](
        count=len(report_list_six_asset_reports), items=report_list_six_asset_reports
    )

    response = ReportHistoryView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200

    # Check table rows
    parent_report = report_list_six_asset_reports[0]
    assertContains(response, parent_report.name)
    assertContains(
        response,
        '<a href="/en/test/objects/detail/?ooi_id=Hostname%7Cinternet%7Cexample.com">example.com</a>',
        html=True,
    )
    assertContains(response, "Close asset report object details")

    # Check asset reports, show only 5
    total_subreports = str(len(report_list_six_asset_reports[0].input_oois))
    child_report_1 = report_list_six_asset_reports[0].input_oois[0]
    child_report_2 = report_list_six_asset_reports[0].input_oois[1]
    child_report_3 = report_list_six_asset_reports[0].input_oois[2]
    child_report_4 = report_list_six_asset_reports[0].input_oois[3]
    child_report_5 = report_list_six_asset_reports[0].input_oois[4]
    child_report_6 = report_list_six_asset_reports[0].input_oois[5]
    assertContains(response, f"5/{total_subreports}")
    assertContains(
        response,
        f"This report consists of {total_subreports} asset reports with the following report types and objects:",
    )
    assertContains(
        response,
        (
            '<a href="/en/test/reports/report-history/subreports?'
            f'report_id={parent_report}" class="button">View all asset reports</a>'
        ),
        html=True,
    )
    assertContains(response, child_report_1)
    assertContains(response, child_report_2)
    assertContains(response, child_report_3)
    assertContains(response, child_report_4)
    assertContains(response, child_report_5)
    assertNotContains(response, child_report_6)

    # Check if all report types are shown
    assertContains(response, "RPKI Report")
    assertContains(response, "Safe Connections Report")
    assertContains(response, "System Report")
    assertContains(response, "Mail Report")
    assertContains(response, "IPv6 Report")
    assertContains(response, "Web System Report")


# Test if the asset reports that belong to one parent are collected well enough
@pytest.mark.skip("The SubreportView is probably not used anymore")
def test_report_history_asset_reports_table(
    rf, client_member, mock_organization_view_octopoes, mocker, report_list_six_asset_reports, get_asset_reports
):
    mocker.patch("account.mixins.OrganizationView.get_katalogus")
    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("subreports", kwargs=kwargs)
    parent_report = report_list_six_asset_reports[0]

    request = rf.get(url, {"report_id": parent_report.primary_key})
    request.resolver_match = resolve(url)

    setup_request(request, client_member.user)

    mock_organization_view_octopoes().query_many.return_value = get_asset_reports

    response = SubreportView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200

    # Check header
    assertContains(
        response,
        f'<a href="/en/test/reports/view?report_id={parent_report}" title="Shows report details">{parent_report}</a>',
        html=True,
    )
    assertContains(response, "<h1>Asset reports</h1>", html=True)
    assertContains(
        response,
        (
            '<a class="button secondary" href="/en/test/reports/report-history/">'
            '<span class="icon icon-chevron-left"></span>Back to Reports History</a>'
        ),
        html=True,
    )

    # Check table rows
    assertContains(
        response,
        '<a href="/en/test/objects/detail/?ooi_id=Hostname%7Cinternet%7Cexample.com">example.com</a>',
        html=True,
    )

    # Check asset reports, show only 5
    total_subreports = str(len(report_list_six_asset_reports[1]))
    child_report_1 = report_list_six_asset_reports[1].input_oois[0]
    child_report_2 = report_list_six_asset_reports[1].input_oois[1]
    child_report_3 = report_list_six_asset_reports[1].input_oois[2]
    child_report_4 = report_list_six_asset_reports[1].input_oois[3]
    child_report_5 = report_list_six_asset_reports[1].input_oois[4]
    child_report_6 = report_list_six_asset_reports[1].input_oois[5]
    assertContains(response, f"Showing {total_subreports} of {total_subreports} asset reports")
    assertContains(response, child_report_1)
    assertContains(response, child_report_2)
    assertContains(response, child_report_3)
    assertContains(response, child_report_4)
    assertContains(response, child_report_5)
    assertContains(response, child_report_6)

    # Check if all report types are shown
    assertContains(response, "RPKI Report")
    assertContains(response, "Safe Connections Report")
    assertContains(response, "System Report")
    assertContains(response, "Mail Report")
    assertContains(response, "IPv6 Report")
    assertContains(response, "Web System Report")


def test_report_history_report_type_summary(
    rf, client_member, mock_organization_view_octopoes, mocker, reports_more_input_oois
):
    mocker.patch("account.mixins.OrganizationView.get_katalogus")
    request = setup_request(rf.get("report_history"), client_member.user)

    mock_organization_view_octopoes().list_reports.return_value = Paginated[HydratedReport](
        count=1, items=[reports_more_input_oois]
    )

    response = ReportHistoryView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200

    assertContains(response, "RPKI Report")
    assertContains(response, "Safe Connections Report")
    assertContains(response, "This report consists of 8 asset reports with the following report types and objects:")
    assertContains(response, "<td>4</td>", html=True)
