import json

from django.urls import reverse
from pytest_django.asserts import assertContains

from rocky.views.ooi_edit import OOIEditView
from tests.conftest import setup_request


def test_ooi_edit(rf, client_member, mock_organization_view_octopoes, network):
    mock_organization_view_octopoes().get.return_value = network

    request = setup_request(rf.get("ooi_edit"), client_member.user)
    response = OOIEditView.as_view()(
        request, organization_code=client_member.organization.code, temporal_context=None, ooi="Network|testnetwork"
    )

    assert response.status_code == 200
    assertContains(response, "testnetwork")
    assertContains(response, "Save testnetwork")


def test_ooi_edit_report_recipe_get(rf, client_member, mock_organization_view_octopoes, report_recipe):
    mock_organization_view_octopoes().get.return_value = report_recipe
    ooi_id = f"ReportRecipe|{report_recipe.recipe_id}"

    request = setup_request(rf.get("ooi_edit"), client_member.user)
    response = OOIEditView.as_view()(
        request, organization_code=client_member.organization.code, temporal_context=None, ooi=ooi_id
    )

    assert response.status_code == 200
    assertContains(response, "Edit: " + ooi_id)


def test_ooi_edit_report_recipe_post(
    rf, client_member, mock_organization_view_octopoes, report_recipe, mocker, mock_scheduler, mock_bytes_client
):
    mock_organization_view_octopoes().get.return_value = report_recipe
    mocker.patch("rocky.views.ooi_view.create_ooi")
    ooi_id = f"ReportRecipe|{report_recipe.recipe_id}"

    request_url = (
        reverse(
            "ooi_edit",
            kwargs={"organization_code": client_member.organization.code, "temporal_context": "now", "ooi": ooi_id},
        )
        + f"?ooi_id={ooi_id}"
    )

    request = setup_request(
        rf.post(
            request_url,
            {
                "ooi_type": "ReportRecipe",
                "user": client_member.user.email,
                "recipe_id": report_recipe.recipe_id,
                "report_type": "test",
                "report_name_format": report_recipe.report_name_format,
                "input_recipe": json.dumps(report_recipe.input_recipe),
                "asset_report_types": json.dumps(report_recipe.asset_report_types),
                "cron_expression": report_recipe.cron_expression,
            },
        ),
        client_member.user,
    )
    response = OOIEditView.as_view()(
        request, organization_code=client_member.organization.code, temporal_context=None, ooi=ooi_id
    )

    assert response.status_code == 302

    response_url = "/en/{}/now/objects/ReportRecipe%7C{}"
    assert response.url == response_url.format(client_member.organization.code, report_recipe.recipe_id)
