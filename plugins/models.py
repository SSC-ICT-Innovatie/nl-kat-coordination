import datetime
import re

import recurrence
import structlog
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Model, QuerySet
from docker.utils import parse_repository_tag
from recurrence.fields import RecurrenceField

from objects.models import Hostname, IPAddress, IPPort, object_type_by_name
from openkat.models import Organization
from tasks.models import ObjectSet, Schedule

logger = structlog.get_logger(__name__)


class ScanLevel(models.IntegerChoices):
    L0 = 0
    L1 = 1
    L2 = 2
    L3 = 3
    L4 = 4


class Plugin(models.Model):
    plugin_id = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)  # TODO: updated_at?

    # Metadata
    name = models.CharField(max_length=64, unique=True)
    description = models.TextField(null=True, blank=True)
    scan_level = models.PositiveSmallIntegerField(choices=ScanLevel, default=ScanLevel.L4)

    # Task specifications
    consumes = ArrayField(models.CharField(max_length=128, blank=True), default=list, blank=True)  # TODO: revise
    recurrences = RecurrenceField(null=True, blank=True)  # If set, this is used as a default
    batch_size = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Override the global BATCH_SIZE setting for this plugin. Set to 0 to disable batching.",
    )

    # Image specifications
    oci_image = models.CharField(max_length=256, null=True)
    oci_arguments = ArrayField(models.CharField(max_length=256, blank=True), default=list)
    version = models.CharField(max_length=16, null=True)  # TODO: drop or use
    permissions = models.JSONField(default=dict)

    objects = models.Manager()

    class Meta:
        permissions = [("run_plugin", "Can run a plugin")]

    def __str__(self):
        return f"{self.plugin_id}"

    def repository(self) -> str | None:
        if not self.oci_arguments:
            return None

        repository, tag = parse_repository_tag(self.oci_image)

        return repository

    def real_version(self) -> str | None:
        if self.version:
            return self.version

        if not self.oci_arguments:
            return None

        repository, tag = parse_repository_tag(self.oci_image)
        # Note: to resolve to the registry, use resolve_repository_name(repository)

        return tag or "latest"

    def types_in_arguments(self) -> list[type[Model] | str]:
        result = []
        models = object_type_by_name()

        for arg in self.oci_arguments:
            is_model = False
            for model_name, model in models.items():
                if "{" + model_name.lower() + "}" in arg.lower():
                    result.append(model)
                    is_model = True
                    break

            if not is_model:
                result.extend(re.findall(r"{([^}]+)}", arg))

        results = set(result)
        results.discard("file")

        return list(results)

    def files_in_arguments(self):
        results = []
        for consume in self.consumes:
            if consume.startswith("file:"):
                results.append(consume.lstrip("file:"))

        return results

    def consumed_types(self) -> list[type[Model] | str]:
        result = self.types_in_arguments()
        for consume in self.consumes:
            is_model = False

            for model_name, model in object_type_by_name().items():
                if not consume.startswith("type:") or consume.lstrip("type:").lower() != model_name.lower():
                    continue

                result.append(model)
                is_model = True
                break

            if not is_model:
                result.extend(re.findall(r"{([^}]+)}", consume))

        results = set(result)
        results.discard("file")

        return list(results)

    def has_enabled_schedules(self, organization: Organization | None = None) -> bool:
        """Check if this plugin has any enabled schedules for the given organization."""
        # Check for schedules matching the specific organization
        if Schedule.objects.filter(plugin=self, organization=organization, enabled=True).exists():
            return True

        # If organization is not None, also check for global schedules (organization=None)
        if organization is not None:
            return Schedule.objects.filter(plugin=self, organization=None, enabled=True).exists()

        return False

    def enabled_organizations(self) -> QuerySet:
        """Get all organizations that have enabled schedules for this plugin."""
        # Get organizations with schedules
        orgs_with_schedules = Organization.objects.filter(schedules__plugin=self, schedules__enabled=True)

        # Check if there are global (organization=None) schedules
        has_global_schedules = Schedule.objects.filter(plugin=self, organization=None, enabled=True).exists()

        if not has_global_schedules:
            return orgs_with_schedules

        # If globally scheduled, return all organizations
        return Organization.objects.all()

    def enable(self) -> list[Schedule]:
        """Create schedules for this plugin globally (organization=None). Alias for schedule()."""
        return self.schedule_for(None)

    def enable_for(self, organization: Organization | None) -> list[Schedule]:
        """Create schedules for this plugin for a specific organization. Alias for schedule_for()."""
        return self.schedule_for(organization)

    def schedule(self) -> list[Schedule]:
        """Create schedules for this plugin globally (organization=None)."""
        return self.schedule_for(None)

    def schedule_for(self, organization: Organization | None) -> list[Schedule]:
        """Create schedules for this plugin for a specific organization."""
        # Check if schedules already exist
        schedules = Schedule.objects.filter(plugin=self, organization=organization)

        if schedules.exists():
            return list(schedules)

        queries: list[tuple[ContentType, str, str]] = []
        consumed_types = self.consumed_types()

        if Hostname in consumed_types:
            consumed_types.remove(Hostname)
            queries.append((ContentType.objects.get_for_model(Hostname), "", "All hostnames"))
        if IPAddress in consumed_types:
            consumed_types.remove(IPAddress)
            queries.append((ContentType.objects.get_for_model(IPAddress), "", "All IPs"))
        if IPPort in consumed_types:
            consumed_types.remove(IPPort)
            queries.append((ContentType.objects.get_for_model(IPPort), "", "All IP Ports"))

        # Schedule object sets
        object_sets = list(
            ObjectSet.objects.filter(name__in=[name for name in consumed_types if isinstance(name, str)])
        )

        # This is possibly the first time enabling the plugin for the organization
        for object_type, query, name in queries:
            new, created = ObjectSet.objects.get_or_create(name=name, object_type=object_type, object_query=query)
            object_sets.append(new)

        created_schedules = []
        for object_set in object_sets:
            schedule = Schedule.objects.create(
                plugin=self,
                enabled=True,
                object_set=object_set,
                organization=organization,
                recurrences=self.recurrences
                if self.recurrences and str(self.recurrences)
                else recurrence.Recurrence(
                    rrules=[recurrence.Rule(recurrence.DAILY)],  # Daily scheduling is the default for plugins
                    dtstart=datetime.datetime.now(datetime.UTC),
                ),
            )
            created_schedules.append(schedule)

        if not object_sets:
            schedule = Schedule.objects.create(
                plugin=self,
                enabled=True,
                organization=organization,
                recurrences=self.recurrences
                if self.recurrences and str(self.recurrences)
                else recurrence.Recurrence(
                    rrules=[recurrence.Rule(recurrence.DAILY)], dtstart=datetime.datetime.now(datetime.UTC)
                ),
            )
            created_schedules.append(schedule)

        return created_schedules


class PluginSettings(models.Model):
    settings = models.JSONField(default=dict)  # TODO: encoder/decoder with for datatimes?
    plugin = models.ForeignKey(Plugin, on_delete=models.CASCADE, related_name="plugin_settings")
    organizations = models.ManyToManyField("openkat.organization", related_name="plugin_settings")


class BusinessRule(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [("run_businessrule", "Can run a business rule")]

    def __str__(self) -> str:
        return self.name
