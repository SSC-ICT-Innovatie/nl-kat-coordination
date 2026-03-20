import structlog
from django import forms
from django.conf import settings
from django.contrib.auth import forms as auth_forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser, Group
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db.utils import IntegrityError
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _
from tools.enums import SCAN_LEVEL
from tools.forms.base import BaseRockyForm, BaseRockyModelForm
from tools.models import (
    GROUP_ADMIN,
    GROUP_CLIENT,
    GROUP_REDTEAM,
    ORGANIZATION_CODE_LENGTH,
    Organization,
    OrganizationMember,
)

from account.validators import get_password_validators_help_texts

logger = structlog.get_logger(__name__)

User = get_user_model()


class UserRegistrationForm(forms.Form):
    """
    Basic User form fields, name, email and password.
    With fields validation.
    """

    name = forms.CharField(
        label=_("Name"),
        max_length=254,
        help_text=_("The name that will be used in order to communicate."),
        widget=forms.TextInput(
            attrs={
                "autocomplete": "off",
                "placeholder": _("Please provide username"),
                "aria-describedby": "explanation-name",
            }
        ),
    )
    email = forms.EmailField(
        label=_("Email"),
        max_length=254,
        help_text=_("Enter an email address."),
        widget=forms.EmailInput(
            attrs={"autocomplete": "off", "placeholder": "name@example.com", "aria-describedby": "explanation-email"}
        ),
    )

    @staticmethod
    def send_password_reset_email(user, organization: Organization):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
      
        subject = _("Set password for your new account.")
        message = render_to_string(
            "registration_email.html",
            {
                "organization": organization,
                "host": request._current_scheme_host(),
                "uid": uid,
                "token": token,
            },
        )

        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)

    def register_user(self) -> AbstractUser:
        return User.objects.create_user(
            full_name=self.cleaned_data.get("name", ""), email=self.cleaned_data.get("email"), password=None
        )


class AccountTypeSelectForm(forms.Form):
    account_type = forms.ModelChoiceField(
        queryset=Group.objects.none(),
        empty_label=_("--- Please select one of the available options ----"),
        label=_("Account type"),
        widget=forms.Select(attrs={"aria-describedby": "explanation-account-type"}),
        error_messages={"required": _("Please select an account type to proceed.")},
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["account_type"].queryset = get_allowed_groups(user)

def get_allowed_groups(user):
    """Lists all groups that are the same, or a subset of the current users group based on
    the permissions associated with it.
    This allows users to create users with less or similar permissons to
    themselves but no higher."""
    user_perms = user.get_all_permissions()
    allowed_groups = []

    for group in Group.objects.all().prefetch_related("permissions"):
        group_perms = {
            f"{perm.content_type.app_label}.{perm.codename}"
            for perm in group.permissions.all()
        }

        if group_perms.issubset(user_perms):
            allowed_groups.append(group)

    return Group.objects.filter(id__in=[g.id for g in allowed_groups])


class TrustedClearanceLevelRadioPawsForm(forms.Form):
    trusted_clearance_level = forms.ChoiceField(
        required=True,
        label=_("Trusted clearance level"),
        choices=[(-1, "Unset")] + SCAN_LEVEL.choices,
        initial=-1,
        help_text=_("Select a clearance level you trust this member with."),
        widget=forms.RadioSelect(attrs={"radio_paws": True}),
        error_messages={"trusted_clearance_level": {"required": _("Please select a clearance level to proceed.")}},
    )


class MemberRegistrationForm(UserRegistrationForm, TrustedClearanceLevelRadioPawsForm):
    field_order = ["name", "email", "trusted_clearance_level"]

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop("organization")
        self.account_type = kwargs.pop("account_type")
        super().__init__(*args, **kwargs)
        if self.account_type != GROUP_REDTEAM:
            self.fields.pop("trusted_clearance_level")

    def create_new_member(self, user: AbstractUser | None = None) -> None:
        """When no user is passed, create a new user as well."""
        try:
            if user is None:
                user = self.register_user()
                # new registered user must set a password through the password reset form.
                self.send_password_reset_email(user, self.organization)

            member = OrganizationMember.objects.create(user=user, organization=self.organization)
            member.groups.add(Group.objects.get(name=self.account_type))

            if self.account_type == GROUP_REDTEAM:
                member.trusted_clearance_level = self.cleaned_data.get("trusted_clearance_level")

            if self.account_type == GROUP_ADMIN:
                member.trusted_clearance_level = 4
                member.acknowledged_clearance_level = 4
            member.save()

        except (IntegrityError, Group.DoesNotExist) as error:
            logger.error("An error occurred, more info: %s", error)
            return None

    def register_member(self) -> None:
        email = self.cleaned_data.get("email")

        try:
            user = User.objects.get(email=email)
            try:
                OrganizationMember.objects.get(user=user, organization=self.organization)
            except OrganizationMember.DoesNotExist:
                self.create_new_member(user)

        # if user does not exist, neither can it be a member, create a new user and member.
        except User.DoesNotExist:
            self.create_new_member()

    def is_valid(self):
        is_valid = super().is_valid()
        if is_valid:
            self.register_member()
        return is_valid


class OrganizationForm(BaseRockyModelForm):
    """
    Form to create a new organization.
    """

    class Meta:
        model = Organization
        fields = ["name", "code"]

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": _("The name of the organization."),
                    "autocomplete": "off",
                    "aria-describedby": _("explanation-organization-name"),
                }
            ),
            "code": forms.TextInput(
                attrs={
                    "placeholder": _("A unique code of maximum {code_length} characters in length.").format(
                        code_length=ORGANIZATION_CODE_LENGTH
                    ),
                    "autocomplete": "off",
                    "aria-describedby": _("explanation-organization-code"),
                }
            ),
        }
        error_messages = {
            "name": {
                "required": _("Organization name is required to proceed."),
                "unique": _("Choose another organization."),
            },
            "code": {
                "required": _("Organization code is required to proceed."),
                "unique": _("Choose another code for your organization."),
            },
        }


class IndemnificationAddForm(BaseRockyForm):
    may_scan = forms.CharField(
        label=_(
            "I declare that OpenKAT may scan the assets of my organization and "
            "that I have permission to scan these assets. "
            "I am aware of the implications a scan (with a higher scan level) brings on my systems."
        ),
        widget=forms.CheckboxInput(),
    )
    am_authorized = forms.CharField(
        label=_(
            "I declare that I am authorized to give this indemnification on behalf of my organization. "
            "I have the experience and knowledge to know what the consequences might be and"
            " can be held responsible for them."
        ),
        widget=forms.CheckboxInput(),
    )


class AssignClearanceLevelForm(BaseRockyForm):
    assigned_level = forms.BooleanField(label=_("Trusted to change Clearance Levels."))


class AcknowledgeClearanceLevelForm(BaseRockyForm):
    acknowledged_level = forms.BooleanField(label=_("Acknowledged to change Clearance Levels."))


class OrganizationMemberEditForm(BaseRockyModelForm, TrustedClearanceLevelRadioPawsForm):
    blocked = forms.BooleanField(
        required=False,
        label=_("Blocked"),
        help_text=_("Set the members status to blocked, so they don't have access to the organization anymore."),
        widget=forms.CheckboxInput(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["blocked"].widget.attrs["field_form_label"] = "Status"
        if self.instance.user.is_superuser:
            self.fields["trusted_clearance_level"].disabled = True
        self.fields["acknowledged_clearance_level"].label = _("Accepted clearance level")
        self.fields["acknowledged_clearance_level"].required = False
        self.fields["acknowledged_clearance_level"].widget.attrs["fixed_paws"] = (
            self.instance.acknowledged_clearance_level
        )
        self.fields["acknowledged_clearance_level"].widget.attrs["class"] = "level-indicator-form"
        if self.instance.user.is_superuser:
            self.fields["trusted_clearance_level"].disabled = True

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.trusted_clearance_level < instance.acknowledged_clearance_level:
            instance.acknowledged_clearance_level = instance.trusted_clearance_level
        if commit:
            instance.save()
        return instance

    class Meta:
        model = OrganizationMember
        fields = ["blocked", "trusted_clearance_level", "acknowledged_clearance_level"]


class OnboardingOrganizationUpdateForm(OrganizationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code"].disabled = True


class OrganizationUpdateForm(OrganizationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code"].disabled = True
        self.fields["tags"].widget.attrs["placeholder"] = _("Enter tags separated by comma.")

    class Meta:
        model = Organization
        fields = ["name", "code", "tags"]


class SetPasswordForm(auth_forms.SetPasswordForm):
    """
    A form that lets a user change set their password without entering the old
    password
    """

    error_messages = {"password_mismatch": _("The two password fields didn’t match.")}
    new_password1 = forms.CharField(
        label=_("New password"),
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "placeholder": _("Enter a new password")}),
        strip=False,
        help_text=get_password_validators_help_texts,
        validators=[validate_password],
    )
    new_password2 = forms.CharField(
        label=_("New password confirmation"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "placeholder": _("Repeat the new password")}),
        help_text=_("Confirm the new password"),
        validators=[validate_password],
    )
