from django.core.management import BaseCommand

from reports.runner.worker import get_runtime_manager


class Command(BaseCommand):
    help = "Start a report worker that pulls tasks from the scheduler to generate reports."

    def handle(self, *args, **options):
        get_runtime_manager().run()
