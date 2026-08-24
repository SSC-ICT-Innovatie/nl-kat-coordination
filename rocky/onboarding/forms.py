from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from tools.forms.settings import SCAN_LEVEL_CHOICES
from tools.models import Organization

from onboarding.view_helpers import DNS_REPORT_LEAST_CLEARANCE_LEVEL

User = get_user_model()


class ClearanceLevelSelect(forms.Select):
    """A custom clearance level selection, disabling some clearance levels"""

    def create_option(self, *args, **kwargs):
        option = super().create_option(*args, **kwargs)
        if option.get("value") != DNS_REPORT_LEAST_CLEARANCE_LEVEL:
            option["attrs"]["disabled"] = "disabled"
        return option


class OnboardingSetClearanceLevelForm(forms.Form):
    level = forms.IntegerField(
        label=_("Clearance level"),
        help_text=_(
            "The clearance level determines how aggressive the object can be "
            "scanned by plugins. A higher clearance level means more aggressive scans are allowed."
        ),
        error_messages={"level": {"required": _("Please select a clearance level to proceed.")}},
        widget=ClearanceLevelSelect(
            choices=SCAN_LEVEL_CHOICES, attrs={"aria-describedby": _("explanation-clearance-level")}
        ),
    )


class OnboardingCreateObjectURLForm(forms.Form):
    """
    Custom URL field form especially for onboarding. No need of web_url and network object.
    """

    # TODO remove once fields dont show optional and or select fields with *no* options anymore
    url = forms.URLField(
        assume_scheme="https",
        label="URL",
        label_suffix="",
        required=True,
        help_text=_("Please enter a valid URL starting with 'http://' or 'https://'."),
        widget=forms.URLInput({"placeholder": "Enter your URL (e.g., https://example.com)"}),
    )


class OrganizationSelectForm(forms.Form):
    """
    Lets an onboarding user pick an existing organization to onboard into,
    instead of being forced to create a new one.
    """

    organization = forms.ModelChoiceField(
        queryset=Organization.objects.none(),
        label=_("Organization"),
        empty_label=_("--- Select an organization ---"),
        error_messages={"organization": {"required": _("Please select an organization to proceed.")}},
        widget=forms.Select(attrs={"aria-describedby": _("explanation-organization-select")}),
    )

    def __init__(self, *args, organizations=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organizations is not None:
            self.fields["organization"].queryset = organizations
