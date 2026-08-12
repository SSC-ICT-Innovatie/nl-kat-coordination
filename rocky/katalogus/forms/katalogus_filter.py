from django import forms
from django.utils.translation import gettext_lazy as _
from tools.forms.base import BaseRockyForm

FILTER_OPTIONS = (("all", _("Show all")), ("enabled", _("Enabled")), ("disabled", _("Disabled")))

SORTING_OPTIONS = (
    ("a-z", "A-Z"),
    ("z-a", "Z-A"),
    ("enabled-disabled", _("Enabled-Disabled")),
    ("disabled-enabled", _("Disabled-Enabled")),
)


class KATalogusFilter(BaseRockyForm):
    """Filter options for plugins listing in KAT-alogus."""

    filter_options = forms.ChoiceField(
        required=False, label=_("Filter options"), choices=FILTER_OPTIONS, widget=forms.RadioSelect()
    )

    sorting_options = forms.ChoiceField(
        required=False, label=_("Sorting options"), choices=SORTING_OPTIONS, widget=forms.RadioSelect()
    )
