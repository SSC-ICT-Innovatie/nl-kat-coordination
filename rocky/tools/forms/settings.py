from django.utils.functional import Promise
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from tools.enums import SCAN_LEVEL

Choice = tuple[str, Promise]
Choices = list[Choice]
ChoicesGroup = tuple[str, Choices]
ChoicesGroups = list[ChoicesGroup]

BLANK_CHOICE = ("", _("--- Please select one of the available options ----"))
FILTER_BLANK_CHOICE = ("", _("--- Show all ----"))

RISK_RATING_CHOICES: Choices = [
    BLANK_CHOICE,
    ("recommendation", _("recommendation")),
    ("low", _("low")),
    ("medium", _("medium")),
    ("high", _("high")),
    ("very high", _("very high")),
    ("critical", _("critical")),
]

PIE_SCALE_EFFORT_CHOICES: Choices = [
    BLANK_CHOICE,
    ("quickfix", _("quickfix")),
    ("low", _("low")),
    ("medium", _("medium")),
    ("high", _("high")),
]

PIE_SCALE_CHOICES: Choices = [BLANK_CHOICE, ("low", _("low")), ("medium", _("medium")), ("high", _("high"))]

CLEARANCE_TYPE_CHOICES = [("declared", _("Declared")), ("inherited", _("Inherited")), ("empty", _("Empty"))]
SCAN_LEVEL_CHOICES = SCAN_LEVEL.choices

MANUAL_FINDING_ID_PREFIX = "KAT-"

FINDING_TYPE_IDS_HELP_TEXT = _("Add one finding type ID per line.")

FINDING_DATETIME_HELP_TEXT = _("Add the date and time of your finding (UTC)")

RAW_FILE_DATETIME_HELP_TEXT = _("Add the date and time of when the raw file was generated (UTC)")

OBSERVED_AT_HELP_TEXT = _(
    "OpenKAT stores a time indication with every observation, "
    "so it is possible to see the status of your network through time. "
    "Select a datetime to change the view to represent that moment in time."
)

BOEFJE_CONTAINER_IMAGE_HELP_TEXT = mark_safe(
    _(
        "<p>The name of the Docker image. For example: <i>'ghcr.io/minvws/openkat/nmap'</i>. "
        "In OpenKAT, all Boefjes with the same container image will be seen as 'variants' and will be "
        "shown together on the Boefje detail page. </p> "
    )
)

BOEFJE_DESCRIPTION_HELP_TEXT = _(
    "A description of the Boefje explaining in short what it can do. "
    "This will both be displayed inside the KAT-alogus and on the Boefje details page."
)


BOEFJE_CONSUMES_HELP_TEXT = _(
    "Select the object type(s) that your Boefje consumes. "
    "To select multiple objects, press and hold the 'ctrl'/'command' key "
    "and then click the items you want to select. "
)

BOEFJE_SCHEMA_HELP_TEXT = mark_safe(
    _(
        "<p>If any other settings are needed for your Boefje, add these as a JSON Schema, "
        "otherwise, leave the field empty or 'null'.</p> "
        "<p> This JSON is used as the basis for a form for the user. "
        "When the user enables this Boefje they can get the option to give extra information. "
        "For example, it can contain an API key that the script requires.</p> "
        "<p>More information about what the schema.json file looks like can be found "
        "<a href='https://docs.openkat.nl/developer_documentation/development_tutorial/creating_a_boefje.html'> "
        "here</a>.</p> "
    )
)

BOEFJE_PRODUCES_HELP_TEXT = mark_safe(
    _(
        "<p>Add a set of mime types that are produced by this Boefje, separated by commas. "
        "For example: <i>'text/html'</i>, <i>'image/jpeg'</i> or <i>'boefje/{boefje-id}'</i></p> "
        "<p>These output mime types will be shown on the Boefje detail page as information for other users. </p> "
    )
)
BOEFJE_SCAN_LEVEL_HELP_TEXT = mark_safe(
    _(
        "<p>Select a clearance level for your Boefje. For more information about the different "
        "clearance levels please check the "
        "<a href='https://docs.openkat.nl/manual/usermanual.html#scan-levels-clearance-indemnities'> "
        "documentation</a>.</p> "
    )
)

BOEFJE_RUN_ON_HELP_TEXT = _(
    "Choose when this Boefje will scan objects. "
    "It can run on a given interval or it can run every time an object "
    "has been created or changed. "
)

DEPTH_DEFAULT = 9
DEPTH_MAX = 15
DEPTH_HELP_TEXT = _("Depth of the tree.")
