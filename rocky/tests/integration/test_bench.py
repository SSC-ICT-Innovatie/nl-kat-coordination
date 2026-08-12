import pytest
from reports.report_types.aggregate_organisation_report.report import AggregateOrganisationReport
from reports.runner.report_runner import aggregate_reports

from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network
from tests.integration.conftest import seed_system


@pytest.mark.slow
def test_aggregate_report_benchmark(octopoes_api_connector, valid_time, organization):
    hostname_range = range(0, 20)
    for x in hostname_range:
        seed_system(
            octopoes_api_connector,
            valid_time,
            test_hostname=f"{x}.com",
            test_ip=f"192.0.{x % 7}.{x % 13}",
            test_ipv6=f"{x % 7}e4d:64a2:cb49:bd48:a1ba:def3:d15d:{x % 5}230",
        )

    reports = [
        x.id for x in AggregateOrganisationReport.reports["required"] + AggregateOrganisationReport.reports["optional"]
    ]
    _, data, _, _ = aggregate_reports(
        octopoes_api_connector,
        [Hostname(name=f"{x}.com", network=Network(name="test").reference).reference for x in hostname_range],
        reports,
        valid_time,
        organization.code,
    )

    assert data["systems"]
