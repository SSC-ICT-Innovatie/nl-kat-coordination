from functools import cached_property

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from knox import crypto
from knox.models import AbstractAuthToken
from knox.settings import CONSTANTS
from tools.enums import MAX_SCAN_LEVEL
from tools.models import Organization, OrganizationMember


class KATUserManager(BaseUserManager):
    """
    Kat user model manager where email is the unique identifiers
    for authentication instead of usernames.
    """

    def create_user(self, email, password, **extra_fields):
        """
        Create and save a User with the given email and password.
        """
        if not email:
            raise ValueError(_("The email must be set"))
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))
        return self.create_user(email, password, **extra_fields)


class LowercaseEmailField(models.EmailField):
    """
    Override EmailField to convert emails to lowercase before saving.
    """

    def to_python(self, value):
        """
        Convert email to lowercase.
        """
        value = super().to_python(value)
        if isinstance(value, str):
            return value.lower()
        return value


class KATUser(AbstractBaseUser, PermissionsMixin):
    # Because we migrated from using the standard Django User model, we need
    # explicitly use AutoField here instead of using BigAutoField by default
    id = models.AutoField(primary_key=True, verbose_name="ID")
    full_name = models.CharField(_("full name"), max_length=150)
    email = LowercaseEmailField(_("email"), max_length=254, unique=True)
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

    objects = KATUserManager()

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
        return self.members.select_related("organization")

    @cached_property
    def organizations(self) -> list[Organization]:
        """
        Lists all organizations a user is a member of, excluding organizations to which access is blocked.

        Superusers and users with the permission can_access_all_organizations are considered to be members
        of all organizations.
        """
        if self.has_perm("tools.can_access_all_organizations"):
            return self.all_organizations
        return [m.organization for m in self.organization_members if not m.blocked]

    @cached_property
    def organizations_including_blocked(self) -> list[Organization]:
        """
        Lists all organizations a user is a member of, including organizations to which access is blocked.

        Superusers and users with the permission can_access_all_organizations are considered to be members
        of all organizations.
        """
        if self.has_perm("tools.can_access_all_organizations"):
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
        """
        Updates token_key and digest with and returns the new token"
        """
        # Code copied from rest-knox AuthTokenManager
        token = crypto.create_token_string()
        self.token_key = token[: CONSTANTS.TOKEN_KEY_LENGTH]
        self.digest = crypto.hash_token(token)

        return token
