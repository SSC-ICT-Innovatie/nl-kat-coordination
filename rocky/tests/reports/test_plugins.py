from unittest.mock import MagicMock

from django.urls import resolve, reverse
from katalogus.client import KATalogusHTTPStatusError
from reports.views.generate_report import SetupScanGenerateReportView

from octopoes.models.pagination import Paginated
from octopoes.models.types import OOIType
from tests.conftest import setup_request


def test_generate_report_setup_scan_wrong_plugin_id(
    rf, client_member, valid_time, mocker, mock_organization_view_octopoes, mock_bytes_client, listed_hostnames
):
    katalogus_client = mocker.patch("account.mixins.OrganizationView.katalogus_client")
    mock_organization_view_octopoes().list_objects.return_value = Paginated[OOIType](
        count=len(listed_hostnames), items=listed_hostnames
    )
    katalogus_client.get_plugins.side_effect = KATalogusHTTPStatusError(MagicMock())
    mock_bytes_client().upload_raw.return_value = "raw_id"

    kwargs = {"organization_code": client_member.organization.code}
    url = reverse("generate_report_setup_scan", kwargs=kwargs)

    request = rf.post(url, {"observed_at": valid_time.strftime("%Y-%m-%d"), "ooi": "all", "report_type": "ipv6-report"})
    request.resolver_match = resolve(url)

    setup_request(request, client_member.user)

    response = SetupScanGenerateReportView.as_view()(request, organization_code=client_member.organization.code)

    assert response.status_code == 307
    assert list(request._messages)[0].message == "An HTTP %d error occurred. Check logs for more info."
