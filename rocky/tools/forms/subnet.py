import ipaddress

from django import forms
from django.utils.translation import gettext_lazy as _

from tools.forms.base import BaseRockyForm

# The smallest mask the nmap range boefjes scan by default (MIN_VLSM_IPV4 in
# kat_nmap_ip_range/kat_nmap_tcp); larger ranges are skipped with a logged
# UnacceptedVSLM, so they are rejected here.
MIN_SCANNABLE_PREFIXLEN_V4 = 22
MIN_SCANNABLE_PREFIXLEN_V6 = 118


class SubnetAddForm(BaseRockyForm):
    """Form for adding a subnet (NetBlock) in two steps.

    Step 1 renders the cidr, network and name fields; step 2 re-renders those
    as hidden fields together with the clearance level, after showing the
    computed IP range for review. The clearance level choices are populated by
    the view so a user can only submit levels up to their own maximum.
    """

    cidr = forms.CharField(label=_("Subnet (CIDR)"), max_length=45, help_text=_("For example 192.168.5.0/24."))
    network = forms.ChoiceField(label=_("Network"), choices=[])
    name = forms.CharField(label=_("Name"), max_length=256, required=False)
    clearance_level = forms.TypedChoiceField(
        label=_("Clearance level"), choices=[], required=False, coerce=int, empty_value=None
    )

    def clean_cidr(self) -> str:
        cidr = self.cleaned_data["cidr"]
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError as error:
            raise forms.ValidationError(_("Enter a valid CIDR, e.g. 192.168.5.0/24.")) from error

        min_prefixlen = MIN_SCANNABLE_PREFIXLEN_V6 if network.version == 6 else MIN_SCANNABLE_PREFIXLEN_V4
        if network.prefixlen < min_prefixlen:
            raise forms.ValidationError(
                _(
                    "Subnet is too large for scanning. Nmap skips ranges larger than a /%(mask)s; "
                    "add smaller blocks instead."
                )
                % {"mask": min_prefixlen}
            )
        return cidr
