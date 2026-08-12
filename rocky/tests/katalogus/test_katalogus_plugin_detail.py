from katalogus.views.plugin_detail import BoefjeDetailView
from pytest_django.asserts import assertContains, assertNotContains

from tests.conftest import setup_request


def test_plugin_detail_view(
    rf,
    superuser_member,
    mock_mixins_katalogus,
    plugin_details,
    boefje_dns_records,
    boefje_nmap_tcp,
    mock_organization_view_octopoes,
    mock_scheduler_client_task_list,
    mocker,
):
    mock_mixins_katalogus.get_plugin.return_value = plugin_details
    katalogus_mocker = mocker.patch("katalogus.client.KATalogusClient")()
    katalogus_mocker.get_plugins.return_value = [boefje_dns_records, boefje_nmap_tcp]

    request = setup_request(rf.get("boefje_detail"), superuser_member.user)
    response = BoefjeDetailView.as_view()(
        request, organization_code=superuser_member.organization.code, plugin_id="test-plugin"
    )

    assertContains(response, "TestBoefje")
    assertContains(response, "Produces")
    assertContains(response, "Tasks")
    assertContains(response, "Object list")
    assertContains(response, "Consumes")
    assertContains(response, plugin_details.description)
    assertNotContains(response, "Container image")
    assertNotContains(response, "Variants")


def test_plugin_detail_view_with_container_image(
    rf,
    superuser_member,
    mocker,
    plugin_details_with_container,
    boefje_dns_records,
    boefje_nmap_tcp,
    mock_organization_view_octopoes,
    mock_scheduler_client_task_list,
):
    katalogus_mocker = mocker.patch("katalogus.client.KATalogus")()
    katalogus_mocker.get_plugin.return_value = plugin_details_with_container
    katalogus_mocker.get_plugins.return_value = [boefje_dns_records, boefje_nmap_tcp]

    request = setup_request(rf.get("boefje_detail"), superuser_member.user)
    response = BoefjeDetailView.as_view()(
        request, organization_code=superuser_member.organization.code, plugin_id="test-plugin"
    )

    assertContains(response, "TestBoefje")
    assertContains(response, "Container image")
    assertContains(response, "Variants")
    assertContains(response, boefje_dns_records.name)
    assertContains(response, boefje_dns_records.oci_arguments[0])
    assertContains(response, boefje_dns_records.oci_arguments[1])
    assertContains(response, boefje_nmap_tcp.name)
    assertContains(response, boefje_nmap_tcp.oci_arguments[0])
    assertContains(response, boefje_nmap_tcp.oci_arguments[1])
    assertContains(response, "Nmap TCP")
    assertContains(response, "Produces")
    assertContains(response, "Tasks")
    assertContains(response, "Object list")
    assertContains(response, "Consumes")
    assertContains(response, plugin_details_with_container.description)


def test_plugin_detail_view_no_consumes(
    rf,
    superuser_member,
    mock_mixins_katalogus,
    mocker,
    plugin_details,
    boefje_dns_records,
    boefje_nmap_tcp,
    mock_organization_view_octopoes,
    mock_scheduler_client_task_list,
):
    plugin_details.consumes = []
    mock_mixins_katalogus.get_plugin.return_value = plugin_details
    katalogus_mocker = mocker.patch("katalogus.client.KATalogusClient")()
    katalogus_mocker.get_plugins.return_value = [boefje_dns_records, boefje_nmap_tcp]

    request = setup_request(rf.get("boefje_detail"), superuser_member.user)
    response = BoefjeDetailView.as_view()(
        request, organization_code=superuser_member.organization.code, plugin_id="test-plugin"
    )

    assertContains(response, "TestBoefje does not need any input objects.")
