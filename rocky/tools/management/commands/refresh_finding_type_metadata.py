"""Schedule the kat-finding-types boefje for existing KATFindingType OOIs.

Finding Type classification (groups and tags) is stored as metadata on
KATFindingType in XTDB. Existing OOIs do not receive new classification
automatically after a catalog or registry change; see
docs/source/developer-documentation/finding-type-groups.md ("Preserving and refreshing
classifications").

Instead of re-running the kat-finding-types boefje by hand, page by page, per
organization, this command queues the boefje for every existing KATFindingType
in every (or a single) organization. The boefjes worker and the
kat_kat_finding_types normalizer then rehydrate the stored OOIs with the
classification from the current catalog.

Run this after deploying catalog or registry changes:

    python manage.py refresh_finding_type_metadata            # all organizations
    python manage.py refresh_finding_type_metadata --organization test
    python manage.py refresh_finding_type_metadata --dry-run  # count only
"""

import logging

from django.conf import settings
from django.core.management import BaseCommand
from django.utils import timezone
from katalogus.client import get_katalogus_client

from octopoes.connector.octopoes import OctopoesAPIConnector
from rocky.scheduler import Boefje as SchedulerBoefje
from rocky.scheduler import BoefjeTask, TaskPush, scheduler_client
from tools.models import Organization

logger = logging.getLogger(__name__)

FINDING_TYPES_BOEFJE_ID = "kat-finding-types"


class Command(BaseCommand):
    help = (
        "Schedule the kat-finding-types boefje for all existing KATFindingType OOIs, so stored "
        "finding types are rehydrated with the current groups and tags from the catalog."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--organization",
            type=str,
            required=False,
            help="Organization code to refresh. Defaults to all organizations.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report how many finding types would be refreshed, without scheduling tasks.",
        )

    def handle(self, *args, **options):
        organization_code = options.get("organization")
        dry_run = options.get("dry_run", False)

        organizations = Organization.objects.all()
        if organization_code:
            organizations = organizations.filter(code=organization_code)
            if not organizations.exists():
                self.stderr.write(f'Unknown organization code: "{organization_code}"')
                return

        valid_time = timezone.now()
        katalogus = get_katalogus_client()
        total_scheduled = 0

        for organization in organizations:
            try:
                plugin = katalogus.get_plugin(organization.code, FINDING_TYPES_BOEFJE_ID)
            except Exception:
                logger.warning("Could not fetch %s for %s", FINDING_TYPES_BOEFJE_ID, organization.code)
                plugin = None

            if plugin is None or not plugin.enabled:
                self.stdout.write(
                    f"[{organization.code}] skipped: {FINDING_TYPES_BOEFJE_ID} is not enabled in KATalogus."
                )
                continue

            connector = OctopoesAPIConnector(
                settings.OCTOPOES_API, client=organization.code, timeout=settings.ROCKY_OUTGOING_REQUEST_TIMEOUT
            )

            # Paginate: list_objects returns at most DEFAULT_LIMIT (50) objects
            # per call, while the catalog holds 88 finding types.
            finding_types = []
            offset = 0
            page_size = 100
            while True:
                page = connector.list_objects({"KATFindingType"}, valid_time=valid_time, offset=offset, limit=page_size)
                finding_types.extend(page.items)
                offset += page_size
                if offset >= page.count or not page.items:
                    break

            if not finding_types:
                self.stdout.write(f"[{organization.code}] no KATFindingType OOIs found.")
                continue

            if dry_run:
                self.stdout.write(f"[{organization.code}] would refresh {len(finding_types)} finding types.")
                total_scheduled += len(finding_types)
                continue

            scheduler = scheduler_client(organization.code)
            for finding_type in finding_types:
                boefje_task = BoefjeTask(
                    # The worker needs the full plugin definition (notably
                    # oci_image) to run the boefje; a bare id is not enough.
                    boefje=SchedulerBoefje.model_validate(plugin.model_dump()),
                    input_ooi=finding_type.reference,
                    organization=organization.code,
                )
                scheduler.push_task(
                    TaskPush(
                        priority=1, data=boefje_task.model_dump(), scheduler_id="boefje", organisation=organization.code
                    )
                )

            total_scheduled += len(finding_types)
            self.stdout.write(f"[{organization.code}] scheduled {len(finding_types)} refresh tasks.")

        verb = "would refresh" if dry_run else "scheduled"
        self.stdout.write(f"Done: {verb} {total_scheduled} finding type(s) in total.")
