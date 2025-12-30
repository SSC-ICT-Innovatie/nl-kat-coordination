import structlog
from django.core.management.base import BaseCommand, CommandParser

from tasks.models import Task, TaskStatus

logger = structlog.getLogger(__name__)


class Command(BaseCommand):
    help = "Cancel and optionally delete (queued) tasks from the database"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--running", "-r", action="store_true", help="Also cancel running tasks besides queued")
        parser.add_argument(
            "--delete", "-d", action="store_true", help="Delete the task database entries after canceling"
        )
        parser.add_argument(
            "--organization", "-o", type=str, help="Only cancel tasks for a specific organization (by id)"
        )

    def handle(self, *args, **options):
        # Determine which statuses to cancel
        statuses = [TaskStatus.QUEUED]
        if options["running"]:
            statuses.extend([TaskStatus.RUNNING])

        # Build the query
        query = Task.objects.filter(status__in=statuses)
        if options["organization"]:
            query = query.filter(organization__id=options["organization"])

        # Get count before processing
        task_count = query.count()

        if task_count == 0:
            self.stdout.write(self.style.WARNING("No tasks found matching the criteria."))
            return

        # Confirm action
        status_text = "queued" if not options["running"] else "queued and running"
        action_text = "cancel and delete" if options["delete"] else "cancel"
        org_text = f" for organization '{options['organization']}'" if options["organization"] else ""

        self.stdout.write(self.style.WARNING(f"About to {action_text} {task_count} {status_text} task(s){org_text}."))

        # Cancel tasks
        cancelled_count = 0
        for task in query:
            try:
                task.cancel()
                cancelled_count += 1
                logger.info("Cancelled task %s", task.pk)
            except Exception as e:
                logger.error("Failed to cancel task %s: %s", task.pk, e)
                self.stdout.write(self.style.ERROR(f"Failed to cancel task {task.pk}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Successfully cancelled {cancelled_count} task(s)."))

        # Delete tasks if requested
        if options["delete"]:
            deleted_count, _ = query.delete()
            self.stdout.write(self.style.SUCCESS(f"Successfully deleted {deleted_count} task(s)."))
