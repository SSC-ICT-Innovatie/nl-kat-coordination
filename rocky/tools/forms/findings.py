import json
from functools import lru_cache
from pathlib import Path

from django import forms
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from octopoes.models.ooi.findings import RiskLevelSeverity
from tools.forms.base import BaseRockyForm

FINDINGS_SEVERITIES_CHOICES = (
    (str(severity.name).lower(), str(severity.value).lower()) for severity in RiskLevelSeverity
)

MUTED_FINDINGS_CHOICES = (
    ("non-muted", _("Show non-muted findings")),
    ("muted", _("Show muted findings")),
    ("all", _("Show muted and non-muted findings")),
)


# The registry and catalog are copied into the Rocky container at build time.
# In a source checkout they are read directly from the same Boefjes files.
FINDING_TYPES_DIR = Path(__file__).resolve().parents[3] / "boefjes/boefjes/plugins/kat_kat_finding_types"


def _read_classification_files() -> tuple[dict, dict]:
    """Read the group registry and finding type catalog shared with Boefjes.

    These files are copied from Boefjes into the Rocky container at build time
    (see rocky/Dockerfile) and cached for the lifetime of the process: restart
    Rocky after changing the registry or catalog. A standalone Rocky checkout
    without the Boefjes files fails here with a clear message instead of a raw
    FileNotFoundError deep inside form rendering.
    """
    try:
        registry = json.loads((FINDING_TYPES_DIR / "finding_type_groups.json").read_text(encoding="utf-8"))
        catalog = json.loads((FINDING_TYPES_DIR / "kat_finding_types.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            "Could not read the finding type groups registry or the finding type catalog from "
            f"{FINDING_TYPES_DIR}. Rocky expects these files to be present; in containers they are "
            "copied from Boefjes at build time (see rocky/Dockerfile), in source checkouts they are "
            "read from boefjes/boefjes/plugins/kat_kat_finding_types/ relative to the repository root."
        ) from error
    return registry, catalog


@lru_cache(maxsize=1)
def _classification_data() -> tuple[dict, dict]:
    """Cache the raw files, not the rendered choices.

    Group labels depend on the request language, so they must be computed per
    request; only the (language-independent) file contents are cached here.
    Restart Rocky after changing the registry or catalog.
    """
    return _read_classification_files()


def finding_classification_choices() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    registry, catalog = _classification_data()
    group_choices = [(identifier, _group_label(group)) for identifier, group in registry.items()]
    tags = sorted({tag for finding_type in catalog.values() for tag in finding_type.get("tags", [])})
    return group_choices, [(tag, tag.replace("-", " ").capitalize()) for tag in tags]


def _group_label(group: dict) -> str:
    """Prefer the Dutch display name when the UI language is Dutch.

    Group names come from the JSON registry instead of gettext, so they are
    stored in both languages there. Fall back to the English name.
    """
    if get_language() and get_language().startswith("nl") and group.get("name_nl"):
        return group["name_nl"]
    return group["name"]


class FindingClassificationForm(BaseRockyForm):
    group = forms.ChoiceField(
        label=_("Filter by group"),
        required=False,
        # Finding types can belong to multiple groups and groups form a
        # hierarchy, but filtering is on explicit membership only (see
        # docs/source/finding-type-groups.md): sub-groups are not included.
        help_text=_("Filters on the selected group only; sub-groups are not included."),
    )
    tag = forms.ChoiceField(label=_("Filter by tag"), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        group_choices, tag_choices = finding_classification_choices()
        self.fields["group"].choices = [("", _("All groups")), *group_choices]
        self.fields["tag"].choices = [("", _("All tags")), *tag_choices]


class FindingSeverityMultiSelectForm(forms.Form):
    severity = forms.MultipleChoiceField(
        label=_("Filter by severity"),
        required=False,
        choices=FINDINGS_SEVERITIES_CHOICES,
        widget=forms.CheckboxSelectMultiple,
    )


class MutedFindingSelectionForm(BaseRockyForm):
    muted_findings = forms.ChoiceField(
        initial="non-muted",
        label=_("Filter by muted findings"),
        required=False,
        choices=MUTED_FINDINGS_CHOICES,
        widget=forms.RadioSelect,
    )


class FindingSearchForm(BaseRockyForm):
    search = forms.CharField(
        label=_("Search"), required=False, max_length=256, help_text=_("Object ID contains (case sensitive)")
    )


class OrderByFindingTypeForm(BaseRockyForm):
    order_by = forms.CharField(widget=forms.HiddenInput(attrs={"value": "finding_type"}), required=False)


class OrderBySeverityForm(BaseRockyForm):
    order_by = forms.CharField(widget=forms.HiddenInput(attrs={"value": "score"}), required=False)
