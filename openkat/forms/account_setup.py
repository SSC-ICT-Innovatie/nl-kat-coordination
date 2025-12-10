from django import forms
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import password_validators_help_text_html, validate_password
from django.utils.translation import gettext_lazy as _

from openkat.enums import SCAN_LEVEL
from openkat.forms.base import BaseOpenKATForm, BaseOpenKATModelForm
from openkat.models import (
    GROUP_ADMIN,
    GROUP_READ_ONLY,
    ORGANIZATION_CODE_LENGTH,
    Organization,
    OrganizationMember,
    User,
)


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
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "off",
                "placeholder": _("Choose a super secret password"),
                "aria-describedby": "explanation-password",
            }
        ),
        help_text=password_validators_help_text_html(),
        validators=[validate_password],
    )

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            self.add_error("email", _("Choose another email."))
        return email

    def register_user(self):
        user = User.objects.create_user(
            full_name=self.cleaned_data.get("name"),
            email=self.cleaned_data.get("email"),
            password=self.cleaned_data.get("password"),
        )
        return user


class AccountTypeSelectForm(forms.Form):
    """
    Shows a dropdown list of account types
    """

    ACCOUNT_TYPE_CHOICES = [
        ("", _("--- Please select one of the available options ----")),
        (GROUP_ADMIN, GROUP_ADMIN),
        (GROUP_READ_ONLY, GROUP_READ_ONLY),
    ]

    account_type = forms.CharField(
        label=_("Account type"),
        error_messages={"group": {"required": _("Please select an account type to proceed.")}},
        widget=forms.Select(choices=ACCOUNT_TYPE_CHOICES, attrs={"aria-describedby": "explanation-account-type"}),
    )


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
    field_order = ["name", "email", "password", "trusted_clearance_level"]

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop("organization")
        self.account_type = kwargs.pop("account_type")
        super().__init__(*args, **kwargs)
        self.fields.pop("trusted_clearance_level")

    def register_member(self):
        user = self.register_user()
        member = OrganizationMember.objects.create(user=user, organization=self.organization)
        member.groups.add(Group.objects.get(name=self.account_type))

        if self.account_type == GROUP_ADMIN:
            member.trusted_clearance_level = 4
            member.acknowledged_clearance_level = 4
        member.save()

    def is_valid(self):
        is_valid = super().is_valid()
        if is_valid:
            self.register_member()
        return is_valid


class OrganizationForm(BaseOpenKATModelForm):
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
                    "placeholder": _("A unique code of {code_length} characters.").format(
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


class AssignClearanceLevelForm(BaseOpenKATForm):
    assigned_level = forms.BooleanField(label=_("Trusted to change Clearance Levels."))


class AcknowledgeClearanceLevelForm(BaseOpenKATForm):
    acknowledged_level = forms.BooleanField(label=_("Acknowledged to change Clearance Levels."))


class OrganizationMemberEditForm(BaseOpenKATModelForm, TrustedClearanceLevelRadioPawsForm):
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
