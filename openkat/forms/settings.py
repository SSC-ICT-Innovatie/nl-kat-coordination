from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

from openkat.enums import SCAN_LEVEL

Choice = tuple[str, Promise]
Choices = list[Choice]
ChoicesGroup = tuple[str, Choices]
ChoicesGroups = list[ChoicesGroup]

BLANK_CHOICE = ("", _("--- Please select one of the available options ----"))
SCAN_LEVEL_CHOICES = [BLANK_CHOICE] + SCAN_LEVEL.choices


OBSERVED_AT_HELP_TEXT = _(
    "OpenKAT stores a time indication with every observation, "
    "so it is possible to see the status of your network through time. "
    "Select a datetime to change the view to represent that moment in time."
)
