import os
from logging.config import dictConfig

from celery import Celery
from celery.signals import setup_logging, worker_shutdown
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "openkat.settings")
app = Celery()
app.config_from_object(settings.CELERY)
app.autodiscover_tasks()


@setup_logging.connect
def config_loggers(*args, **kwargs):
    dictConfig(settings.LOGGING)


@worker_shutdown.connect
def cancel_all_tasks(*args, **kwargs):
    from tasks.models import Task, TaskStatus  # noqa: PLC0415

    for task in Task.objects.filter(status__in=[TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.RUNNING]):
        task.cancel()


app.conf.beat_schedule = {
    "schedule-scan-profile-recalculations": {
        "task": "tasks.tasks.schedule_scan_profile_recalculations",
        "schedule": settings.SCAN_LEVEL_RECALCULATION_INTERVAL,
        "args": tuple(),
        "options": {"queue": settings.QUEUE_NAME_RECALCULATIONS},
    },
    "schedule-organization-attribution": {
        "task": "tasks.tasks.schedule_attribution",
        "schedule": settings.ATTRIBUTION_INTERVAL,
        "args": tuple(),
        "options": {"queue": settings.QUEUE_NAME_RECALCULATIONS},
    },
    "reschedule": {
        "task": "tasks.tasks.reschedule",
        "schedule": settings.SCHEDULE_INTERVAL,
        "args": tuple(),
        "options": {"queue": settings.QUEUE_NAME_SCHEDULE},
    },
}
