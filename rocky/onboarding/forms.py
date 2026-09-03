import ipaddress
from urllib.parse import urlparse

from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from tools.forms.settings import SCAN_LEVEL_CHOICES

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

    def clean_url(self):
        # The onboarding flow runs a DNS report, which requires a hostname.
        # An IP-address host (e.g. http://127.0.0.1) would crash later in
        # get_ooi_pks with a KeyError, so reject it at the trust boundary.
        url = self.cleaned_data["url"]
        host = urlparse(url).hostname
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return url
        raise forms.ValidationError(_("The onboarding DNS report requires a hostname, not an IP address."))
