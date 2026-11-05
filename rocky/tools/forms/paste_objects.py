from django import forms
from django.utils.translation import gettext_lazy as _

from tools.forms.base import BaseRockyForm

CLEARANCE_LEVEL_EMPTY_LABEL = _("--- Unchanged (no scan level requested) ----")
CLEARANCE_LEVEL_CHOICES = [(str(level), f"L{level}") for level in range(5)]


class PasteObjectsForm(BaseRockyForm):
    objects = forms.CharField(
        label=_("Objects"),
        widget=forms.Textarea(
            attrs={"rows": 10, "placeholder": "192.0.2.10\n2001:db8::1\nexample.com\nhttps://example.com/"}
        ),
        help_text=_(
            "One object per line, or separated by commas. Each value may be an IPv4 or IPv6 address, "
            "a subnet, a hostname or a URL. The type of each value is detected automatically."
        ),
        required=True,
    )
    network = forms.ChoiceField(
        label=_("Network"), choices=[], help_text=_("Created objects belong to this network."), required=True
    )
    clearance_level = forms.ChoiceField(
        label=_("Clearance level"),
        # The full list (including the empty option) is built per member
        # in the view, based on the member's maximum level.
        choices=CLEARANCE_LEVEL_CHOICES,
        help_text=_("Requested scan level for the new objects. Other values are ignored."),
        required=False,
    )
