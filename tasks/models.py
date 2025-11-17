import uuid
from typing import Any

import recurrence.fields
import structlog
from celery import Celery
from celery.result import AsyncResult
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import QuerySet
from djangoql.exceptions import DjangoQLError
from djangoql.queryset import apply_search

from files.models import File
from objects.models import NoOrgQLSchema

logger = structlog.get_logger(__name__)


class TaskStatus(models.TextChoices):
    # Task has been created but not yet queued
    PENDING = "pending"

    # Task has been pushed onto the queue
    QUEUED = "queued"

    # Task has been picked up by a worker
    RUNNING = "running"

    # Task has been completed
    COMPLETED = "completed"

    # Task has failed
    FAILED = "failed"

    # Task has been cancelled
    CANCELLED = "cancelled"


class Operation(models.TextChoices):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class ObjectSet(models.Model):
    """Composite-like model representing a set of objects that can be used as an input for tasks"""

    name = models.CharField(max_length=100, blank=True, null=True, unique=True)
    description = models.TextField(blank=True)
    object_type: models.ForeignKey = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_query = models.TextField(null=True, blank=True)

    # concrete objects
    all_objects = ArrayField(models.CharField(), default=list, blank=True)

    def get_query_objects(self, queryset: QuerySet | None = None, **filters: Any) -> QuerySet:
        if self.object_query is None:
            return self.object_type.model_class().objects.none()

        if queryset is None:
            queryset = self.object_type.model_class().objects.all().filter(**filters)
        else:
            if queryset.model != self.object_type.model_class():
                return self.object_type.model_class().objects.none()

            queryset = queryset.filter(**filters)

        if self.object_query == "":
            return queryset

        try:
            return apply_search(queryset, self.object_query, NoOrgQLSchema)
        except DjangoQLError as e:
            logger.warning("Invalid DjangoQL query: %s", str(e))
            return queryset

    def traverse_objects(self, queryset: QuerySet | None = None, **filters: Any) -> list[int]:
        return list(set(self.all_objects).union({x.pk for x in self.get_query_objects(queryset, **filters)}))

    def __str__(self):
        return self.name or super().__str__()


class Schedule(models.Model):
    enabled = models.BooleanField(default=True)
    recurrences = recurrence.fields.RecurrenceField(null=True, blank=True)
    task_type = models.CharField(max_length=32, default="plugin")  # "plugin" or "report"

    organization = models.ForeignKey(
        "openkat.organization", on_delete=models.CASCADE, related_name="schedules", null=True, blank=True
    )
    plugin = models.ForeignKey["Plugin"](
        "plugins.plugin", on_delete=models.CASCADE, related_name="schedules", null=True, blank=True
    )
    object_set = models.ForeignKey(ObjectSet, on_delete=models.CASCADE, related_name="schedules", null=True, blank=True)
    run_on = models.CharField(max_length=64, null=True, blank=True)
    operation = models.CharField(max_length=16, choices=Operation, null=True, blank=True)

    # Report-specific fields
    report_name = models.CharField(max_length=255, null=True, blank=True)
    report_description = models.TextField(blank=True)
    report_finding_types = ArrayField(models.CharField(max_length=255), default=list, blank=True)

    def run(self) -> list["Task"]:
        # Import here to prevent circular imports
        from tasks.tasks import run_schedule  # noqa: PLC0415

        return run_schedule(self)


class Task(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    schedule = models.ForeignKey(Schedule, on_delete=models.SET_NULL, related_name="tasks", null=True, blank=True)
    organization = models.ForeignKey(
        "openkat.organization", on_delete=models.CASCADE, related_name="tasks", null=True, blank=True
    )
    type = models.CharField(max_length=32, default="plugin")
    data = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=TaskStatus, default=TaskStatus.PENDING)

    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True)
    modified_at = models.DateTimeField(auto_now=True)

    _async_result: AsyncResult | None = None

    @property
    def async_result(self, celery: Celery | None = None) -> AsyncResult:
        if self._async_result is not None:
            return self._async_result

        if not celery:
            from tasks.celery import app  # noqa: PLC0415

            celery = app

        self._async_result = AsyncResult(str(self.id), app=celery)

        return self._async_result

    def cancel(self):
        # Import here to prevent circular imports
        from tasks.celery import app  # noqa: PLC0415

        self.status = TaskStatus.CANCELLED
        self.save()
        app.control.revoke(str(self.id), terminate=True)

    def done(self) -> bool:
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]


class TaskResult(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="task_results")
    file = models.OneToOneField(File, on_delete=models.CASCADE, related_name="task_result")
