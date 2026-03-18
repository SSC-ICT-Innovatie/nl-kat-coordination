import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import structlog
from django.conf import settings
from django.core.management import BaseCommand
from django.db.utils import IntegrityError
from httpx import HTTPStatusError
from pydantic import ValidationError
from tools.models import Organization
from tools.ooi_helpers import create_ooi

from crisis_room.models import FINDINGS_DASHBOARD_NAME, FINDINGS_DASHBOARD_TEMPLATE, Dashboard, DashboardItem
from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models.ooi.reports import ReportRecipe
from rocky.bytes_client import get_bytes_client
from rocky.scheduler import ReportTask, ScheduleRequest, scheduler_client

logger = structlog.get_logger(__name__)


def create_findings_dashboard_recipe(
    organization: Organization, octopoes_client: OctopoesAPIConnector | None = None
) -> str | None:
    """
    Creates a recipe OOI based on default recipe from recipe_seeder.json.
    Creates a schedule of this recipe so the Report can be created to populate data for the Findings Dashboard.
    Returns the recipe UUID string.
    """
    try:
        path = Path(__file__).parent / "recipe_seeder.json"

        with path.open("r") as recipe_seeder:
            recipe_default = json.load(recipe_seeder)

        valid_time = datetime.now(timezone.utc)
        if octopoes_client is None:
            octopoes_client = OctopoesAPIConnector(
                settings.OCTOPOES_API, organization.code, timeout=settings.ROCKY_OUTGOING_REQUEST_TIMEOUT
            )
        bytes_client = get_bytes_client(organization.code)

        report_recipe = ReportRecipe(recipe_id=uuid4(), **recipe_default)

        create_ooi(api_connector=octopoes_client, bytes_client=bytes_client, ooi=report_recipe, observed_at=valid_time)

        schedule_recipe(organization, report_recipe)

        return str(report_recipe.recipe_id)

    except (ValueError, ValidationError, HTTPStatusError, ConnectionError) as error:
        logger.error("An error occurred: %s", error)
    return None


def schedule_recipe(organization: Organization, recipe: ReportRecipe) -> None:
    try:
        valid_time = datetime.now(timezone.utc)
        recipe_id = str(recipe.recipe_id)

        report_task = ReportTask(organisation_id=organization.code, report_recipe_id=recipe_id).model_dump()

        schedule_request = ScheduleRequest(
            scheduler_id="report",
            organisation=organization.code,
            data=report_task,
            schedule=recipe.cron_expression,
            deadline_at=valid_time.isoformat(),
        )

        scheduler_client(organization.code).post_schedule(schedule=schedule_request)
        logger.info("Schedule created for recipe: %s")

    except (ValueError, ValidationError, HTTPStatusError, ConnectionError) as error:
        logger.error("An error occurred: %s", error)


def reschedule_recipe(organization: Organization, recipe_id: str) -> None:
    try:
        scheduler_connector = scheduler_client(organization.code)
        deadline_at = datetime.now(timezone.utc).isoformat()

        filters = {"filters": [{"column": "data", "field": "report_recipe_id", "operator": "==", "value": recipe_id}]}

        schedule = scheduler_connector.post_schedule_search(filters)

        if not schedule.results:
            logger.error("Schedule with recipe id: %s not found.", recipe_id)
            return None

        schedule = schedule.results[0]

        if not schedule.enabled:
            logger.error("A schedule with recipe id: %s is disabled. Enable schedule first.", recipe_id)
            return None

        scheduler_connector.patch_schedule(schedule_id=str(schedule.id), params={"deadline_at": deadline_at})

    except (ValueError, ValidationError, HTTPStatusError, ConnectionError) as error:
        logger.error("An error occurred: %s", error)
    return None


def create_findings_dashboard(
    organization: Organization,
    octopoes_client: OctopoesAPIConnector | None = None,
    DashboardModel=Dashboard,
    DashboardItemModel=DashboardItem,
) -> None:
    dashboard = DashboardModel.objects.create(name=FINDINGS_DASHBOARD_NAME, organization=organization)
    recipe_id = create_findings_dashboard_recipe(organization, octopoes_client)
    DashboardItemModel.objects.create(
        dashboard=dashboard, recipe=recipe_id, template=FINDINGS_DASHBOARD_TEMPLATE, findings_dashboard=True, position=1
    )
    logger.info("New reecipe with id: %s has been created and scheduled.", recipe_id)


def run_findings_dashboard(
    organization: Organization,
    octopoes_client: OctopoesAPIConnector | None = None,
    DashboardModel=Dashboard,
    DashboardItemModel=DashboardItem,
) -> None:
    """
    Find a findings dashboard, if found, take the recipe id and rerun the schedule.
    If no findings dashboard is found, then create a new one and create a new recipe.
    """
    try:
        dashboard = DashboardModel.objects.filter(
            dashboarditem__findings_dashboard=True, organization=organization
        ).first()
        if dashboard is not None:
            findings_dashboard = DashboardItemModel.objects.get(dashboard=dashboard, findings_dashboard=True)
            reschedule_recipe(organization, str(findings_dashboard.recipe))
            logger.info("Recipe %s has been rescheduled.", findings_dashboard.recipe)
        else:
            create_findings_dashboard(organization, octopoes_client, DashboardModel, DashboardItemModel)

    except DashboardItemModel.DoesNotExist:
        create_findings_dashboard(organization, octopoes_client, DashboardModel, DashboardItemModel)

    except (IntegrityError, ValueError, ValidationError):
        logger.exception("Findings Dashboard not created.")


class Command(BaseCommand):
    def handle(self, *args, **options):
        organizations = Organization.objects.all()
        for organization in organizations:
            run_findings_dashboard(organization)
