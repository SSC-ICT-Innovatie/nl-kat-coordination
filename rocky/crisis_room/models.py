import json
from typing import Any, Literal, TypedDict
from urllib.parse import urlencode

import structlog
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models.query_utils import Q
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from tools.models import Organization

logger = structlog.get_logger(__name__)


class Dashboard(models.Model):
    name = models.CharField(blank=False, max_length=126)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    EVENT_CODES = {"created": 900301, "updated": 900302, "deleted": 900303}

    class Meta:
        unique_together = ["name", "organization"]

    def __str__(self) -> str:
        if self.name:
            return f"{self.name} for organization {self.organization}"
        return super().__str__()


MIN_POSITION = 1
MAX_POSITION = 16
FINDINGS_DASHBOARD_NAME = _("Findings Dashboard")
FINDINGS_DASHBOARD_TEMPLATE = "findings_report/report.html"


class DashboardItemSettings(TypedDict):
    size: int
    columns: list[str]


def get_default_dashboard_item_settings() -> DashboardItemSettings:
    default_settings: DashboardItemSettings = {"size": 1, "columns": []}
    return default_settings


class DashboardItem(models.Model):
    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, null=True)
    name = models.CharField(blank=True, max_length=126)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    recipe = models.UUIDField(blank=True, null=True)
    source = models.CharField(blank=True, max_length=126)
    query = models.CharField(blank=True)
    template = models.CharField(blank=True, max_length=126, default=FINDINGS_DASHBOARD_TEMPLATE)
    position = models.PositiveSmallIntegerField(
        blank=True,
        validators=[MinValueValidator(MIN_POSITION), MaxValueValidator(MAX_POSITION)],
        help_text=_(
            "Where on the dashboard do you want to show the data? "
            "Position {} is the most top level and the max position is {}."
        ).format(MIN_POSITION, MAX_POSITION),
    )
    settings = models.JSONField(blank=True, null=True, default=get_default_dashboard_item_settings)
    display_in_crisis_room = models.BooleanField(
        default=False, help_text=_("Will be displayed on the general crisis room, for all organizations.")
    )
    display_in_dashboard = models.BooleanField(
        default=False, help_text=_("Will be displayed on a single organization dashboard")
    )
    findings_dashboard = models.BooleanField(
        default=False, help_text=_("Will be displayed on the findings dashboard for all organizations")
    )

    EVENT_CODES = {"created": 900311, "updated": 900312, "deleted": 900313}

    class Meta:
        permissions = [("change_dashboarditem_position", _("Can change position up or down of a dashboard item."))]
        constraints = [
            models.UniqueConstraint(
                name="unique dashboard position",
                fields=["dashboard", "position"],
                deferrable=models.Deferrable.DEFERRED,
            ),
            models.UniqueConstraint(
                name="unique dashboard name", fields=["dashboard", "name"], deferrable=models.Deferrable.DEFERRED
            ),
            models.UniqueConstraint(
                fields=["dashboard"],
                condition=Q(findings_dashboard=True),
                name="unique_findings_dashboard_per_dashboard",
            ),
        ]

    def __str__(self) -> str:
        try:
            if self.name:
                return f"{self.name} on dashboard {str(self.dashboard)}"
            else:
                return f"Dashboard item on dashboard {str(self.dashboard)}"
        except Dashboard.DoesNotExist:
            return super().__str__()

    @property
    def get_query_url(self) -> str:
        if self.query:
            return urlencode(json.loads(self.query), doseq=True)
        return ""

    @property
    def get_query(self) -> dict[str, Any]:
        if self.query:
            return json.loads(self.query)
        return {}

    def clean(self) -> None:
        if self.recipe and self.query:
            raise ValidationError(_("You have to choose between a recipe or a query, but not both."))
        if self.query and not self.source:
            raise ValidationError(_("You have set a query and not where it is from. Also set the source."))
        if not self.recipe and not self.source and not self.query:
            raise ValidationError(_("DashboardItem must contain at least a 'recipe' or a 'source' with a 'query'."))
        return super().clean()

    def update_position(self, move: Literal["up", "down"]) -> None:
        if move not in ("up", "down"):
            raise ValueError

        old_position = self.position
        new_position = self.position + (-1 if move == "up" else 1)

        if 1 <= new_position <= 16:
            try:
                old_item = DashboardItem.objects.get(dashboard=self.dashboard, position=old_position)
                new_item = DashboardItem.objects.get(dashboard=self.dashboard, position=new_position)

                with transaction.atomic():
                    new_item.position = old_position
                    self.position = new_position
                    new_item.save(update_fields=["position"])
                    self.save(update_fields=["position"])

                logger.info(
                    "Dashboard item %s has been swapped with %s of dashboard %s",
                    old_item.name,
                    new_item.name,
                    old_item.dashboard,
                )
            except DashboardItem.DoesNotExist:
                return

        logger.info("Dashboard item position updated", dashboard_item_id=self.id, event_code="900310")


def get_dashboard_item_positions(instance: DashboardItem) -> list[int]:
    return list(DashboardItem.objects.filter(dashboard=instance.dashboard).values_list("position", flat=True))


@receiver(pre_save, sender=DashboardItem)
def dashboard_item_pre_save(sender, instance, *args, **kwargs):
    if instance._state.adding:  # not when updating
        positions = get_dashboard_item_positions(instance)
        position = max(positions, default=0) + 1
        if position <= MAX_POSITION:
            instance.position = position
        else:
            raise ValidationError(_("Max dashboard items reached."))


@receiver(post_delete, sender=DashboardItem)
def dashboard_item_post_delete(sender, instance, *args, **kwargs):
    """Change the position of the other items on the dashboard after deleting one object."""
    with transaction.atomic():
        try:
            dashboard_items = DashboardItem.objects.filter(
                dashboard=instance.dashboard, position__gte=instance.position
            )
            if dashboard_items:
                dashboard_items.update(position=models.F("position") - 1)

        except (Dashboard.DoesNotExist, instance.DoesNotExist):
            return
