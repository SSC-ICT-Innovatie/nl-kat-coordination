from collections.abc import Iterable
from functools import cached_property
from typing import Any

import structlog
import tagulous.models
from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, Group, Permission, PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.db.models.manager import Manager
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from knox import crypto
from knox.models import AbstractAuthToken
from knox.settings import CONSTANTS

from openkat.enums import MAX_SCAN_LEVEL

GROUP_ADMIN = "admin"
GROUP_READ_ONLY = "read-only"

logger = structlog.get_logger(__name__)

ORGANIZATION_CODE_LENGTH = 32
DENY_ORGANIZATION_CODES = [
    "admin",
    "api",
    "i18n",
    "privacy-statement",
    "account",
    "crisis-room",
    "findings",
    "objects",
    "organizations",
    "edit",
    "members",
    "settings",
    "scans",
    "upload",
    "tasks",
    "tasks",
    "objects",
    "openkat",
]


class LowerCaseCharField(models.CharField):
    """Override CharField to convert value to lowercase before saving."""

    def to_python(self, value: Any | None) -> str | None:
        """Convert email to lowercase."""
        str_value: str = super().to_python(value)
        if str_value is None:
            return None

        return str_value.lower()

    def pre_save(self, model_instance: models.Model, add: bool) -> str | None:  # noqa: FBT001, ARG002
        value: str | None = getattr(model_instance, self.attname)
        if value:
            value = value.lower()
            setattr(model_instance, self.attname, value)
        return value


class LowerCaseEmailField(LowerCaseCharField, models.EmailField):
    """Override EmailField to convert email addresses to lowercase before saving."""


class LowerCaseSlugField(LowerCaseCharField, models.SlugField):
    """Override SlufField to convert slugs to lowercase before saving."""


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
    id = models.BigAutoField(db_column="_id", primary_key=True, serialize=False, verbose_name="ID")
    name = models.CharField(max_length=126, unique=True, help_text=_("The name of the organisation"))
    code = LowerCaseSlugField(
        max_length=ORGANIZATION_CODE_LENGTH,
        unique=True,
        allow_unicode=True,
        help_text=_(
            "A slug containing only lower-case unicode letters, numbers, hyphens or underscores "
            "that will be used in URLs and paths"
        ),
    )
    tags = tagulous.models.TagField(to=OrganizationTag, blank=True)

    EVENT_CODES = {"created": 900201, "updated": 900202, "deleted": 900203}

    def __str__(self) -> str:
        return str(self.name)

    class Meta:
        permissions = (
            ("can_scan_organization", "Can scan organization"),
            ("can_set_clearance_level", "Can set clearance level"),
            ("can_access_all_organizations", "Can access all organizations"),
            ("can_enable_disable_schedule", "Can enable or disable schedules"),
        )

    def save(
        self,
        force_insert: bool = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        super().save(force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields)
        from objects.models import XTDBOrganization  # noqa: PLC0415

        xtdb_org, created = XTDBOrganization.objects.get_or_create(id=self.id, name=self.name, code=self.code)
        xtdb_org.tags = list(self.tags.all().values_list("name", flat=True))
        for tag in xtdb_org.tags._tags:
            tag.save()

        xtdb_org.save(force_insert=force_insert, force_update=force_update, update_fields=update_fields)

    def delete(self, using=None, keep_parents=False):
        super().delete(using=using, keep_parents=keep_parents)
        from objects.models import XTDBOrganization  # noqa: PLC0415

        XTDBOrganization.objects.filter(pk=self.pk).delete()

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
    user = models.ForeignKey("User", on_delete=models.PROTECT, related_name="members")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="members")
    groups = models.ManyToManyField(Group, blank=True)
    blocked = models.BooleanField(default=False)
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

    class Meta:
        unique_together = ["user", "organization"]

    def __str__(self) -> str:
        return str(self.user)


class UserManager(BaseUserManager):
    """
    Kat user model manager where email is the unique identifiers
    for authentication instead of usernames.
    """

    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a User with the given email and password.
        """
        if not email:
            raise ValueError(_("The Email must be set"))
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    full_name = models.CharField(_("full name"), max_length=150)
    email = LowerCaseEmailField(_("email"), max_length=254, unique=True)
    is_staff = models.BooleanField(
        _("staff status"), default=False, help_text=_("Designates whether the user can log into this admin site.")
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. Unselect this instead of deleting accounts."
        ),
    )
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)
    clearance_level = models.IntegerField(
        default=-1,
        help_text=_("The clearance level of the user for all organizations."),
        validators=[MinValueValidator(-1), MaxValueValidator(MAX_SCAN_LEVEL)],
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    objects = UserManager()

    members: Manager["OrganizationMember"]

    EVENT_CODES = {"created": 900101, "updated": 900102, "deleted": 900103}

    def get_full_name(self):
        return self.full_name

    @cached_property
    def all_organizations(self) -> list[Organization]:
        return list(Organization.objects.all())

    @cached_property
    def organization_members(self) -> list[OrganizationMember]:
        """
        Lists the user's OrganizationMembers including the related Organizations.
        """
        return list(self.members.select_related("organization"))

    @property
    def can_access_all_organizations(self) -> bool:
        return self.has_perm("openkat.can_access_all_organizations")

    @cached_property
    def organizations(self) -> list[Organization]:
        """
        Lists all organizations a user is a member of, excluding organizations to which access is blocked.

        Superusers and users with the permission can_access_all_organizations are considered to be members
        of all organizations.
        """
        if self.can_access_all_organizations:
            return self.all_organizations
        return [m.organization for m in self.organization_members if not m.blocked]

    @cached_property
    def organizations_including_blocked(self) -> list[Organization]:
        """
        Lists all organizations a user is a member of, including organizations to which access is blocked.

        Superusers and users with the permission can_access_all_organizations are considered to be members
        of all organizations.
        """
        if self.has_perm("openkat.can_access_all_organizations"):
            return self.all_organizations
        return [m.organization for m in self.organization_members]


class AuthToken(AbstractAuthToken):
    name = models.CharField(_("name"), max_length=150)

    class Meta:
        constraints = [models.UniqueConstraint("user", Lower("name"), name="unique name")]

    EVENT_CODES = {"created": 900111, "updated": 900122, "deleted": 900123}

    def __str__(self) -> str:
        return f"{self.name} ({self.user})"

    def generate_new_token(self) -> str:
        """Updates token_key and digest with and returns the new token"""

        # Code copied from rest-knox AuthTokenManager
        token = crypto.create_token_string()
        self.token_key = token[: CONSTANTS.TOKEN_KEY_LENGTH]
        self.digest = crypto.hash_token(token)

        return token
