from katalogus.views.boefje_setup import AddBoefjeVariantView, AddBoefjeView, EditBoefjeView
from pytest_django.asserts import assertContains

from tests.conftest import setup_request


def test_boefje_setup(rf, superuser_member):
    request = setup_request(rf.get("boefje_setup"), superuser_member.user)
    response = AddBoefjeView.as_view()(request, organization_code=superuser_member.organization.code)

    assert response.status_code == 200
    assertContains(response, "Boefje setup")
    assertContains(response, "Container image")
    assertContains(response, "Name")
    assertContains(response, "Description")
    assertContains(response, "Arguments")
    assertContains(response, "JSON Schema")
    assertContains(response, "Input object type")
    assertContains(response, "Output mime types")
    assertContains(response, "Clearance level")
    assertContains(response, "Create new Boefje")


def test_boefje_variant_setup(rf, superuser_member, boefje_dns_records, mocker):
    katalogus_mocker = mocker.patch("katalogus.client.KATalogusClient")()
    katalogus_mocker.get_plugin.return_value = boefje_dns_records
    request = setup_request(rf.get("boefje_variant_setup"), superuser_member.user)
    response = AddBoefjeVariantView.as_view()(
        request, organization_code=superuser_member.organization.code, plugin_id=boefje_dns_records.id
    )

    assert response.status_code == 200
    assertContains(response, "Boefje variant setup")
    assertContains(response, "Container image")
    assertContains(response, "Name")
    assertContains(response, "Description")
    assertContains(response, "Arguments")
    assertContains(response, "JSON Schema")
    assertContains(response, "Input object type")
    assertContains(response, "Output mime types")
    assertContains(response, "Clearance level")
    assertContains(response, "Create variant")


def test_edit_boefje_view(rf, superuser_member, boefje_dns_records, mocker):
    katalogus_mocker = mocker.patch("katalogus.client.KATalogusClient")()
    katalogus_mocker.get_plugin.return_value = boefje_dns_records
    request = setup_request(rf.get("edit_boefje"), superuser_member.user)
    response = EditBoefjeView.as_view()(
        request, organization_code=superuser_member.organization.code, plugin_id=boefje_dns_records.id
    )

    assert response.status_code == 200
    assertContains(response, "Edit")
    assertContains(response, boefje_dns_records.name)
    assertContains(response, "Container image")
    assertContains(response, "Name")
    assertContains(response, "Description")
    assertContains(response, "Arguments")
    assertContains(response, "JSON Schema")
    assertContains(response, "Input object type")
    assertContains(response, "Output mime types")
    assertContains(response, "Clearance level")
    assertContains(response, "Save changes")
