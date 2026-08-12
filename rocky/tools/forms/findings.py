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
