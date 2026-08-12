from django import forms
from django.utils.translation import gettext_lazy as _

from octopoes.models.types import ALL_TYPES
from tools.enums import SCAN_LEVEL
from tools.forms.base import BaseRockyForm
from tools.forms.settings import (
    BOEFJE_CONSUMES_HELP_TEXT,
    BOEFJE_CONTAINER_IMAGE_HELP_TEXT,
    BOEFJE_DESCRIPTION_HELP_TEXT,
    BOEFJE_PRODUCES_HELP_TEXT,
    BOEFJE_RUN_ON_HELP_TEXT,
    BOEFJE_SCAN_LEVEL_HELP_TEXT,
    BOEFJE_SCHEMA_HELP_TEXT,
)

OOI_TYPE_CHOICES = sorted((ooi_type.get_object_type(), ooi_type.get_object_type()) for ooi_type in ALL_TYPES)
SCAN_TYPE_CHOICES = [("interval", "Run on interval, every:"), ("run_on", "Run on object creation/change:")]
INTERVAL_CHOICES = [
    ("minutes", "minutes"),
    ("hours", "hours"),
    ("days", "days"),
    ("weeks", "weeks"),
    ("years", "years"),
]
OBJECT_CHANGE_CHOICES = [("create", "Creation"), ("update", "Change"), ("create-update", "Creation and change")]


class BoefjeSetupForm(BaseRockyForm):
    oci_image = forms.CharField(required=True, label=_("Container image"), help_text=BOEFJE_CONTAINER_IMAGE_HELP_TEXT)
    name = forms.CharField(required=True, label=_("Name"))
    description = forms.CharField(
        required=False,
        label=_("Description"),
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text=BOEFJE_DESCRIPTION_HELP_TEXT,
    )
    oci_arguments = forms.CharField(
        required=False,
        label=_("Arguments"),
        widget=forms.TextInput(
            attrs={"description": _("For example: -sTU --top-ports 1000"), "aria-describedby": "input-description"}
        ),
    )
    boefje_schema = forms.JSONField(required=False, label=_("JSON Schema"), help_text=BOEFJE_SCHEMA_HELP_TEXT)
    consumes = forms.CharField(
        required=False,
        label=_("Input object type"),
        widget=forms.SelectMultiple(choices=OOI_TYPE_CHOICES),
        help_text=BOEFJE_CONSUMES_HELP_TEXT,
    )
    produces = forms.CharField(required=False, label=_("Output mime types"), help_text=BOEFJE_PRODUCES_HELP_TEXT)
    scan_level = forms.CharField(
        required=False,
        label=_("Clearance level"),
        widget=forms.Select(choices=SCAN_LEVEL.choices),
        help_text=BOEFJE_SCAN_LEVEL_HELP_TEXT,
    )
    scan_type = forms.CharField(
        required=False,
        label=_("Scan type"),
        widget=forms.RadioSelect(
            choices=SCAN_TYPE_CHOICES, attrs={"class": "radio-choice", "data-choicegroup": "runon_selector"}
        ),
        help_text=BOEFJE_RUN_ON_HELP_TEXT,
        initial="interval",
    )
    interval_number = forms.CharField(
        required=False,
        label=_("Interval amount"),
        widget=forms.TextInput(
            attrs={
                "description": _(
                    "Specify the scanning interval for this Boefje. The default is 24 hours. "
                    "For example: 5 minutes will let the Boefje scan every 5 minutes."
                ),
                "class": "runon_selector interval",
            }
        ),
    )
    interval_frequency = forms.CharField(
        required=False,
        label=_("Interval frequency"),
        widget=forms.Select(choices=INTERVAL_CHOICES, attrs={"class": "runon_selector interval"}),
    )
    run_on = forms.CharField(
        required=False,
        label=_("Object creation/change"),
        widget=forms.Select(
            choices=OBJECT_CHANGE_CHOICES,
            attrs={
                "description": _("Choose weather the Boefje should run after creating and/or changing an object. "),
                "class": "runon_selector run_on",
            },
        ),
    )
