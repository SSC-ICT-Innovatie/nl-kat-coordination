import json

from pytest_django.asserts import assertContains
from reports.views.base import ViewReportView
from reports.views.multi_report import (
    MultiReportView,
    OOISelectionMultiReportView,
    ReportTypesSelectionMultiReportView,
    SetupScanMultiReportView,
)

from octopoes.models.pagination import Paginated
from octopoes.models.types import OOIType
from tests.conftest import setup_request


def test_multi_report_select_oois(
    rf, client_member, valid_time, mock_organization_view_octopoes, report_data_ooi_org_a, report_data_ooi_org_b
):
    """
    Will send the selected oois to the report type selection page.
    """

    oois = [report_data_ooi_org_a, report_data_ooi_org_b]
    oois_selection = [ooi.primary_key for ooi in oois]

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](count=len(oois), items=oois)

    request = setup_request(
        rf.post(
            "multi_report_select_report_types", {"observed_at": valid_time.strftime("%Y-%m-%d"), "ooi": oois_selection}
        ),
        client_member.user,
    )

    response = ReportTypesSelectionMultiReportView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200

    total_objects = str(len(oois_selection))

    assertContains(response, f"You have selected {total_objects} objects in the previous step.")


def test_multi_report_select_oois_with_query(
    rf, client_member, valid_time, mock_organization_view_octopoes, report_data_ooi_org_a, report_data_ooi_org_b
):
    """
    Will send the query to the report type selection page.
    """

    oois = [report_data_ooi_org_a, report_data_ooi_org_b]

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](count=len(oois), items=oois)

    request = setup_request(
        rf.post(
            "multi_report_select_report_types",
            {"observed_at": valid_time.strftime("%Y-%m-%d"), "object_selection": "query"},
        ),
        client_member.user,
    )

    response = ReportTypesSelectionMultiReportView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200
    assert response.context_data["selected_oois"] == []

    assertContains(response, "You have selected a live set in the previous step.")
    assertContains(response, "this live set results in 0 objects.")


def test_multi_report_change_ooi_selection(
    rf, client_member, valid_time, mock_organization_view_octopoes, report_data_ooi_org_a, report_data_ooi_org_b
):
    """
    Will send the selected oois back to the ooi selection page.
    """

    oois = [report_data_ooi_org_a, report_data_ooi_org_b]
    oois_selection = [ooi.primary_key for ooi in oois]

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](count=len(oois), items=oois)

    request = setup_request(
        rf.post("multi_report_select_oois", {"observed_at": valid_time.strftime("%Y-%m-%d"), "ooi": oois_selection}),
        client_member.user,
    )

    response = OOISelectionMultiReportView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 200

    for response_ooi in response.context_data["selected_oois"]:
        assert response_ooi in oois_selection


def test_multi_report_report_types_selection(
    rf, client_member, valid_time, mock_organization_view_octopoes, report_data_ooi_org_a, report_data_ooi_org_b, mocker
):
    """
    Will send the selected report types to the configuration page (set plugins).
    """

    mocker.patch("account.mixins.OrganizationView.katalogus_client")

    oois = [report_data_ooi_org_a, report_data_ooi_org_b]

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](count=len(oois), items=oois)

    request = setup_request(
        rf.post(
            "multi_report_setup_scan",
            {"observed_at": valid_time.strftime("%Y-%m-%d"), "report_type": ["multi-organization-report"]},
        ),
        client_member.user,
    )

    response = SetupScanMultiReportView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 307  # if all plugins are enabled the view will auto redirect to generate report

    # Redirect to export setup
    assert response.headers["Location"] == "/en/test/reports/multi-report/export-setup/?"


def test_save_multi_report(
    rf,
    client_member,
    valid_time,
    mock_organization_view_octopoes,
    mocker,
    mock_bytes_client,
    report_data_ooi_org_a,
    report_data_ooi_org_b,
    multi_report_ooi,
):
    """
    Will send data through post to multi report.
    """

    mocker.patch("account.mixins.OrganizationView.katalogus_client")
    oois = [report_data_ooi_org_a, report_data_ooi_org_b]
    oois_selection = [ooi.primary_key for ooi in oois]

    mock_bytes_client().upload_raw.return_value = multi_report_ooi.data_raw_id

    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](count=len(oois), items=oois)

    request = setup_request(
        rf.post(
            "multi_report_view",
            {
                "observed_at": valid_time.strftime("%Y-%m-%d"),
                "ooi": oois_selection,
                "report_type": ["multi-organization-report"],
                "start_date": "2024-01-01",
                "start_time": "10:10",
                "recurrence": "once",
                "parent_report_name_format": "${report_type} for ${oois_count} objects",
            },
        ),
        client_member.user,
    )

    response = MultiReportView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 302  # after post follows redirect, this to first create report ID
    assert "/reports/scheduled-reports/" in response.url


def test_view_multi_report(
    rf,
    client_member,
    mock_organization_view_octopoes,
    mock_bytes_client,
    mock_katalogus_client,
    multi_report_ooi,
    get_multi_report_post_processed_data,
):
    mock_organization_view_octopoes().get_report.return_value = multi_report_ooi
    mock_bytes_client().get_raws.return_value = [
        ("7b305f0d-c0a7-4ad5-af1e-31f81fc229c2", json.dumps(get_multi_report_post_processed_data).encode("utf-8"))
    ]

    request = setup_request(rf.get("view_report", {"report_id": f"{multi_report_ooi.primary_key}"}), client_member.user)

    response = ViewReportView.as_view()(request, organization_code=client_member.organization.code)
    assert response.status_code == 200

    assertContains(response, "Sector Report")
    assertContains(response, "This is the OpenKAT report")

    assertContains(
        response,
        f'<p>Created with data from: <strong>{multi_report_ooi.date_generated.strftime("%b. %d, %Y")}</strong></p>',
        html=True,
    )
    assertContains(
        response,
        f'<p>Created with data from: <strong>{multi_report_ooi.date_generated.strftime("%b. %d, %Y")}</strong></p>',
        html=True,
    )
    assertContains(
        response,
        "<p>This sector contains 2 scanned organizations. The basic security scores are around 71%. "
        "A total of 0 critical vulnerabilities have been identified.</p>",
        html=True,
    )

    assertContains(
        response,
        """
        <section id="summary">
            <div>
                <h2>Summary</h2>
                <dl>
                    <div>
                        <dt>Organisations in sector report</dt>
                        <dd>
                            2
                        </dd>
                    </div>

                    <div>
                        <dt>IP addresses scanned</dt>
                        <dd>
                            3
                        </dd>
                    </div>
                    <div>
                        <dt>Domains scanned</dt>
                        <dd>
                            2
                        </dd>
                    </div>
                    <div>
                        <dt>General recommendations</dt>
                        <dd>
                            7
                        </dd>
                    </div>
                    <div>
                        <dt>Best scoring security check</dt>
                        <dd>
                            CSP Present
                        </dd>
                    </div>
                    <div>
                        <dt>Worst scoring security check</dt>
                        <dd>
                            DNSSEC Present
                        </dd>
                    </div>
                </dl>
            </div>
        </section>
        """,
        html=True,
    )

    assertContains(
        response,
        """
        <section id="open-ports">
            <div>
                <h2>Open ports</h2>
                <p>See an overview of open ports found over all systems and the services these systems provide.</p>

                    <div class="horizontal-scroll">
                        <table>
                            <caption class="visually-hidden">Overview of detected open ports</caption>
                            <thead>
                                <tr>
                                    <th scope="col">Open ports</th>
                                    <th scope="col">Occurrences (IP addresses)</th>
                                    <th scope="col">Services</th>
                                </tr>
                            </thead>
                            <tbody>

                                    <tr>
                                        <td>3306</td>
                                        <td>1/3</td>
                                        <td>MYSQL</td>
                                    </tr>

                                    <tr>
                                        <td>53</td>
                                        <td>1/3</td>
                                        <td>DOMAIN</td>
                                    </tr>

                                    <tr>
                                        <td>443</td>
                                        <td>2/3</td>
                                        <td>HTTPS</td>
                                    </tr>

                                    <tr>
                                        <td>22</td>
                                        <td>1/3</td>
                                        <td>SSH</td>
                                    </tr>

                                    <tr>
                                        <td>80</td>
                                        <td>2/3</td>
                                        <td>HTTP</td>
                                    </tr>

                            </tbody>
                        </table>
                    </div>

            </div>
        </section>

        """,
        html=True,
    )
