"""Regression tests for the refresh_finding_type_metadata management command.

These tests cover the migration path for existing deployments: every stored
KATFindingType must be rehydrated, in every organization, regardless of how
many there are (the Octopoes API caps list results at 50 per page).
"""

from unittest.mock import Mock

from octopoes.models.ooi.findings import KATFindingType
from octopoes.models.pagination import Paginated

FINDING_TYPES_BOEFJE_ID = "kat-finding-types"


def _plugin(enabled=True):
    plugin = Mock()
    plugin.enabled = enabled
    plugin.model_dump.return_value = {
        "id": FINDING_TYPES_BOEFJE_ID,
        "name": "KAT Finding Types",
        "version": None,
        "oci_image": "docker.underdark.nl/librekat/openkat-generic:latest",
    }
    return plugin


def test_command_refreshes_all_pages_and_organizations(mocker, db, organization, organization_b):
    """Both organizations get tasks for every finding type, across pages."""
    connector = mocker.patch(
        "tools.management.commands.refresh_finding_type_metadata.OctopoesAPIConnector"
    ).return_value

    def list_objects(types, valid_time, offset=0, limit=50):
        # 150 finding types per organization: with the command's page size of
        # 100 this forces two pages, proving pagination works.
        total = 150
        items = [KATFindingType(id=f"KAT-PAGE-{i}") for i in range(offset, min(offset + limit, total))]
        return Paginated[KATFindingType](count=total, items=items)

    connector.list_objects.side_effect = list_objects

    katalogus = mocker.patch(
        "tools.management.commands.refresh_finding_type_metadata.get_katalogus_client"
    ).return_value
    katalogus.get_plugin.return_value = _plugin()

    scheduler = mocker.patch("tools.management.commands.refresh_finding_type_metadata.scheduler_client").return_value

    from django.core.management import call_command

    call_command("refresh_finding_type_metadata")

    # Every page was consumed: exactly two calls per organization.
    assert connector.list_objects.call_count == 4
    # One task per finding type per organization: 2 * 150.
    assert scheduler.push_task.call_count == 300
    # The full plugin definition (with oci_image) is queued, not a bare id.
    pushed_boefje = scheduler.push_task.call_args.args[0].data["boefje"]
    assert pushed_boefje["oci_image"] == "docker.underdark.nl/librekat/openkat-generic:latest"
    assert pushed_boefje["id"] == FINDING_TYPES_BOEFJE_ID


def test_command_dry_run_does_not_schedule(mocker, db, organization):
    connector = mocker.patch(
        "tools.management.commands.refresh_finding_type_metadata.OctopoesAPIConnector"
    ).return_value
    connector.list_objects.return_value = Paginated[KATFindingType](
        count=2, items=[KATFindingType(id="KAT-A"), KATFindingType(id="KAT-B")]
    )

    katalogus = mocker.patch(
        "tools.management.commands.refresh_finding_type_metadata.get_katalogus_client"
    ).return_value
    katalogus.get_plugin.return_value = _plugin()

    scheduler = mocker.patch("tools.management.commands.refresh_finding_type_metadata.scheduler_client").return_value

    from django.core.management import call_command

    call_command("refresh_finding_type_metadata", "--dry-run")

    scheduler.push_task.assert_not_called()


def test_command_skips_organizations_without_enabled_plugin(mocker, db, organization):
    connector = mocker.patch(
        "tools.management.commands.refresh_finding_type_metadata.OctopoesAPIConnector"
    ).return_value

    katalogus = mocker.patch(
        "tools.management.commands.refresh_finding_type_metadata.get_katalogus_client"
    ).return_value
    katalogus.get_plugin.return_value = _plugin(enabled=False)

    scheduler = mocker.patch("tools.management.commands.refresh_finding_type_metadata.scheduler_client").return_value

    from django.core.management import call_command

    call_command("refresh_finding_type_metadata")

    connector.list_objects.assert_not_called()
    scheduler.push_task.assert_not_called()


def test_command_handles_empty_organizations(mocker, db, organization):
    connector = mocker.patch(
        "tools.management.commands.refresh_finding_type_metadata.OctopoesAPIConnector"
    ).return_value
    connector.list_objects.return_value = Paginated[KATFindingType](count=0, items=[])

    katalogus = mocker.patch(
        "tools.management.commands.refresh_finding_type_metadata.get_katalogus_client"
    ).return_value
    katalogus.get_plugin.return_value = _plugin()

    scheduler = mocker.patch("tools.management.commands.refresh_finding_type_metadata.scheduler_client").return_value

    from django.core.management import call_command

    call_command("refresh_finding_type_metadata")

    assert connector.list_objects.call_count == 1
    scheduler.push_task.assert_not_called()
