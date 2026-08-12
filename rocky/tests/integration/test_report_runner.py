import json

from reports.runner.report_runner import LocalReportRunner

from octopoes.api.models import Declaration
from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models.ooi.reports import ReportRecipe
from rocky.health import ServiceHealth
from rocky.scheduler import ReportTask
from tests.integration.conftest import seed_system


def test_run_report_task(octopoes_api_connector: OctopoesAPIConnector, report_runner: LocalReportRunner, valid_time):
    oois = seed_system(octopoes_api_connector, valid_time)
    report_runner.bytes_client.health.return_value = ServiceHealth(service="bytes", healthy=True)
    report_runner.bytes_client.upload_raw.return_value = "abcdabcd-f8ab-4bdf-9b1b-58cd98ef6342"

    recipe = ReportRecipe(
        recipe_id="abc4e52b-812c-4cc2-8196-35fb8efc63ca",
        report_type="concatenated-report",
        report_name_format="Concatenated report for ${oois_count} objects",
        input_recipe={"input_oois": [oois["hostnames"][0].reference, oois["hostnames"][1].reference]},
        asset_report_types=["dns-report"],
        cron_expression="* * * * *",
    )
    octopoes_api_connector.save_declaration(Declaration(ooi=recipe, valid_time=valid_time))

    task = ReportTask(organisation_id=octopoes_api_connector.client, report_recipe_id=str(recipe.recipe_id))
    report_runner.run(task)

    assert len(report_runner.bytes_client.upload_raw.mock_calls) == 3

    assert report_runner.bytes_client.upload_raw.mock_calls[0].kwargs["manual_mime_types"] == {"openkat/report"}
    assert report_runner.bytes_client.upload_raw.mock_calls[1].kwargs["manual_mime_types"] == {"openkat/report"}
    assert report_runner.bytes_client.upload_raw.mock_calls[2].kwargs["manual_mime_types"] == {"openkat/report"}

    data = json.loads(report_runner.bytes_client.upload_raw.mock_calls[0].kwargs["raw"])
    data2 = json.loads(report_runner.bytes_client.upload_raw.mock_calls[1].kwargs["raw"])
    data["input_data"]["plugins"]["required"] = set(data["input_data"]["plugins"]["required"])  # ordering issues
    data2["input_data"]["plugins"]["required"] = set(data2["input_data"]["plugins"]["required"])  # ordering issues

    first_asset_calls = [
        {
            "report_data": {
                "input_ooi": "Hostname|test|example.com",
                "records": [],
                "security": {"spf": True, "dkim": True, "dmarc": True, "dnssec": True, "caa": True},
                "finding_types": [],
            },
            "input_data": {
                "input_oois": ["Hostname|test|example.com"],
                "report_types": ["dns-report"],
                "plugins": {"required": {"dns-records", "dns-sec"}, "optional": ["dns-zone"]},
            },
        },
        {
            "report_data": {
                "input_ooi": "Hostname|test|a.example.com",
                "records": [],
                "security": {"spf": True, "dkim": True, "dmarc": True, "dnssec": True, "caa": True},
                "finding_types": [],
            },
            "input_data": {
                "input_oois": ["Hostname|test|a.example.com"],
                "report_types": ["dns-report"],
                "plugins": {"required": {"dns-records", "dns-sec"}, "optional": ["dns-zone"]},
            },
        },
    ]
    assert data in first_asset_calls
    assert data2 in first_asset_calls

    data_report = {
        "input_data": {
            "input_oois": {
                "AssetReport|Hostname|test|example.com|dns-report",
                "AssetReport|Hostname|test|a.example.com|dns-report",
            },
            "report_types": ["dns-report"],
            "plugins": {"required": {"dns-records", "dns-sec"}, "optional": ["dns-zone"]},
        }
    }

    report_data = json.loads(report_runner.bytes_client.upload_raw.mock_calls[2].kwargs["raw"])
    # ordering issues
    report_data["input_data"]["plugins"]["required"] = set(report_data["input_data"]["plugins"]["required"])
    report_data["input_data"]["input_oois"] = set(report_data["input_data"]["input_oois"])

    assert report_data == data_report

    reports = octopoes_api_connector.list_reports(valid_time)
    assert reports.count == 1

    assert reports.items[0].name == "Concatenated report for 2 objects"
    asset_reports = reports.items[0].input_oois
    assert len(asset_reports) == 2

    assert "DNS Report for a.example.com" in {x.name for x in asset_reports}

    # FIXME: the naming logic in reports/views/mixins.py 107-112 is not right. We expect to find example.com in this
    #  set, but instead only find a.example.com because when ooi_name is 'example.com', the check:
    #  `ooi_name in default_name` also passes for 'DNS Report for Hostname|test|a.example.com in %Y'.
    #  We shouldn't have to guess the match in the report_names argument. The name should be overridden on an object
    #  in the report_data list probably. Note that sometimes this does work when the OOIs are ordered differently.
