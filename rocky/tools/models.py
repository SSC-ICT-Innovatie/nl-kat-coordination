from collections.abc import Iterable
from functools import cached_property

import structlog
import tagulous.models
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from tools.add_ooi_information import SEPARATOR, InformationUpdateError, get_info
from tools.enums import MAX_SCAN_LEVEL
from tools.fields import LowerCaseSlugField

GROUP_ADMIN = "admin"
GROUP_REDTEAM = "redteam"
GROUP_CLIENT = "clients"

logger = structlog.get_logger(__name__)

ORGANIZATION_CODE_LENGTH = 32
DENY_ORGANIZATION_CODES = [
    "admin",
    "api",
    "i18n",
    "health",
    "privacy-statement",
    "account",
    "crisis-room",
    "onboarding",
    "indemnifications",
    "findings",
    "objects",
    "organizations",
    "edit",
    "members",
    "settings",
    "scans",
    "upload",
    "tasks",
    "bytes",
    "kat-alogus",
    "boefjes",
    "mula",
    "octopoes",
    "rocky",
]


class OrganizationTag(tagulous.models.TagTreeModel):
    COLOR_CHOICES = settings.TAG_COLORS
    BORDER_TYPE_CHOICES = settings.TAG_BORDER_TYPES

    color = models.CharField(choices=COLOR_CHOICES, max_length=20, default=COLOR_CHOICES[0][0])
    border_type = models.CharField(choices=BORDER_TYPE_CHOICES, max_length=20, default=BORDER_TYPE_CHOICES[0][0])

    class TagMeta:
        force_lowercase = True
        protect_all = True

    @property
    def css_class(self):
        return f"tags-{self.color} {self.border_type}"


class Organization(models.Model):
    id: int
    name = models.CharField(max_length=126, unique=True, help_text=_("The name of the organization."))
    code = LowerCaseSlugField(
        max_length=ORGANIZATION_CODE_LENGTH,
        unique=True,
        allow_unicode=True,
        help_text=_(
            "A short code containing only lower-case unicode letters, numbers, hyphens or underscores "
            "that will be used in URLs and paths."
        ),
    )
    tags = tagulous.models.TagField(to=OrganizationTag, blank=True)

    EVENT_CODES = {"created": 900201, "updated": 900202, "deleted": 900203}

    def __str__(self) -> str:
        return str(self.name)

    class Meta:
        permissions = (
            ("can_switch_organization", "Can switch organization"),
            ("can_scan_organization", "Can scan organization"),
            ("can_enable_disable_boefje", "Can enable or disable boefje"),
            ("can_add_boefje", "Can add new or duplicate boefjes"),
            ("can_set_clearance_level", "Can set clearance level"),
            ("can_delete_oois", "Can delete oois"),
            ("can_mute_findings", "Can mute findings"),
            ("can_view_katalogus_settings", "Can view KAT-alogus settings"),
            ("can_set_katalogus_settings", "Can set KAT-alogus settings"),
            ("can_recalculate_bits", "Can recalculate bits"),
            ("can_access_all_organizations", "Can access all organizations"),
            ("can_enable_disable_schedule", "Can enable or disable schedules"),
        )
        ordering = ["name"]

    def get_absolute_url(self):
        return reverse("organization_settings", args=[self.pk])

    def clean(self):
        if self.code in DENY_ORGANIZATION_CODES:
            raise ValidationError(
                {
                    "code": _(
                        "This organization code is reserved by OpenKAT and cannot be used. "
                        "Choose another organization code."
                    )
                }
            )


class OrganizationMember(models.Model):
    # New is the status after an e-mail invite has been created for a member but the invite hasn't been accepted yet.
    # Active is when the member has accepted the invited or the account was created directly without an invite.
    # Blocked is when an organization admin has blocked the member.
    class STATUSES(models.TextChoices):
        ACTIVE = "active", _("active")
        NEW = "new", _("new")

    user = models.ForeignKey("account.KATUser", on_delete=models.PROTECT, related_name="members")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="members")
    groups = models.ManyToManyField(Group, blank=True)
    status = models.CharField(choices=STATUSES.choices, max_length=64, default=STATUSES.NEW)
    blocked = models.BooleanField(default=False)
    onboarded = models.BooleanField(default=False)
    trusted_clearance_level = models.IntegerField(
        default=-1, validators=[MinValueValidator(-1), MaxValueValidator(MAX_SCAN_LEVEL)]
    )
    acknowledged_clearance_level = models.IntegerField(
        default=-1, validators=[MinValueValidator(-1), MaxValueValidator(MAX_SCAN_LEVEL)]
    )

    EVENT_CODES = {"created": 900211, "updated": 900212, "deleted": 900213}

    @cached_property
    def all_permissions(self) -> set[str]:
        if self.user.is_active and self.user.is_superuser:
            # Superuser always has all permissions
            return {
                f"{ct}.{name}" for ct, name in Permission.objects.values_list("content_type__app_label", "codename")
            }

        if self.blocked or not self.user.is_active:
            # A blocked or inactive user doesn't have any permissions specific to this organization
            organization_member_perms = set()
        else:
            organization_member_perms = {
                f"{ct}.{name}"
                for ct, name in Permission.objects.filter(group__organizationmember=self).values_list(
                    "content_type__app_label", "codename"
                )
            }
        return organization_member_perms | self.user.get_all_permissions()

    def has_perm(self, perm: str) -> bool:
        return perm in self.all_permissions

    def has_perms(self, perm_list: Iterable[str]) -> bool:
        return all(self.has_perm(perm) for perm in perm_list)

    @property
    def max_clearance_level(self) -> int:
        """The maximum clearance level the user has for this organization.

        When the user has an organization specific clearance level that is lower
        than the global clearance level this will overrule the global clearance
        level.

        For the organization specific clearance level we take the minimum
        of the trusted clearance level and acknowledged clearance level. If the
        user did not acknowledge a changed clearance level, we need to use the
        level that was previously. If an admin lowered the users clearance
        level, we also need to use that level instead of the previously
        acknowledged level.
        """
        if self.trusted_clearance_level == -1 and self.acknowledged_clearance_level == -1:
            return self.user.clearance_level
        else:
            return min(self.trusted_clearance_level, self.acknowledged_clearance_level)

    def has_clearance_level(self, level: int) -> bool:
        return level <= self.max_clearance_level

    @property
    def can_add_dashboard(self):
        return self.has_perm("crisis_room.add_dashboard")

    @property
    def can_change_dashboard(self):
        return self.has_perm("crisis_room.change_dashboard")

    @property
    def can_delete_dashboard(self):
        return self.has_perm("crisis_room.delete_dashboard")

    @property
    def can_reposition_dashboard_item(self):
        return self.has_perm("crisis_room.change_dashboarditem_position")

    @property
    def can_add_dashboard_item(self):
        return self.has_perm("crisis_room.add_dashboarditem")

    @property
    def can_delete_dashboard_item(self):
        return self.has_perm("crisis_room.delete_dashboarditem")

    @property
    def can_change_dashboard_item(self):
        return self.has_perm("crisis_room.change_dashboarditem")

    @property
    def can_modify_dashboard(self) -> bool:
        """If you can add, you might as well change and delete a dashboard."""
        return self.has_perms(
            ["crisis_room.add_dashboard", "crisis_room.change_dashboard", "crisis_room.delete_dashboard"]
        )

    @property
    def can_modify_dashboard_item(self) -> bool:
        """If you can add, you might as well change and delete a dashboard items."""
        return self.has_perms(
            [
                "crisis_room.add_dashboarditem",
                "crisis_room.change_dashboarditem",
                "crisis_room.delete_dashboarditem",
                "crisis_room.change_dashboarditem_position",
            ]
        )

    class Meta:
        unique_together = ["user", "organization"]

    def __str__(self) -> str:
        return str(self.user)


class Indemnification(models.Model):
    user = models.ForeignKey("account.KATUser", on_delete=models.SET_NULL, null=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True)

    EVENT_CODES = {"created": 900221, "updated": 900222, "deleted": 900223}


class OOIInformation(models.Model):
    id = models.CharField(max_length=256, primary_key=True)
    last_updated = models.DateTimeField(auto_now=True)
    data = models.JSONField(null=True)
    consult_api = models.BooleanField(default=False)

    EVENT_CODES = {"created": 900231, "updated": 900232, "deleted": 900233}

    def save(self, *args, **kwargs):
        if self.data is None:
            self.data = {"description": ""}
        if self.consult_api:
            self.consult_api = False
            self.get_internet_description()
        super().save(*args, **kwargs)

    def clean(self):
        if "description" not in self.data:
            raise ValidationError("Description is missing in data")

    @property
    def type(self):
        return self.id.split(SEPARATOR)[0]

    @property
    def value(self):
        return SEPARATOR.join(self.id.split(SEPARATOR)[1:])

    @property
    def description(self):
        if not self.data["description"]:
            self.get_internet_description()
            self.save()
        return self.data["description"]

    def get_internet_description(self):
        try:
            self.data.update(get_info(ooi_type=self.type, natural_key=self.value))
        except InformationUpdateError:
            # we keep the old data if we already have some and can't update
            if not self.data["description"]:
                self.data = {"description": ""}

    def __str__(self) -> str:
        return self.id
