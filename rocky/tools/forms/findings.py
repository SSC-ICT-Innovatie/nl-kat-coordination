import json
from functools import lru_cache
from pathlib import Path

from django import forms
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


@lru_cache(maxsize=1)
def finding_classification_choices() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    registry = json.loads((FINDING_TYPES_DIR / "finding_type_groups.json").read_text(encoding="utf-8"))
    catalog = json.loads((FINDING_TYPES_DIR / "kat_finding_types.json").read_text(encoding="utf-8"))
    group_choices = [(identifier, group["name"]) for identifier, group in registry.items()]
    tags = sorted({tag for finding_type in catalog.values() for tag in finding_type.get("tags", [])})
    return group_choices, [(tag, tag.replace("-", " ").capitalize()) for tag in tags]


class FindingClassificationForm(BaseRockyForm):
    group = forms.ChoiceField(label=_("Filter by group"), required=False)
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
