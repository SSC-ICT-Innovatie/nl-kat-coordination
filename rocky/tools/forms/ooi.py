from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _

from octopoes.models import OOI
from rocky.scheduler import ScheduleResponse
from tools.forms.base import BaseRockyForm, CheckboxTable, LabeledCheckboxInput, ObservedAtForm
from tools.forms.settings import DEPTH_DEFAULT, DEPTH_HELP_TEXT, DEPTH_MAX, SCAN_LEVEL_CHOICES


class OOIReportSettingsForm(ObservedAtForm):
    depth = forms.IntegerField(
        initial=DEPTH_DEFAULT, min_value=1, max_value=DEPTH_MAX, required=False, help_text=DEPTH_HELP_TEXT
    )


class OoiTreeSettingsForm(OOIReportSettingsForm):
    ooi_type = forms.MultipleChoiceField(label=_("Filter types"), widget=forms.CheckboxSelectMultiple(), required=False)

    def __init__(self, ooi_types: list[str], *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.set_ooi_types(ooi_types)

    def set_ooi_types(self, ooi_types: list[str]) -> None:
        if not ooi_types:
            self.fields.pop("ooi_type", None)
            return
        ooi_types_choices = [(type_, type_) for type_ in ooi_types]
        self.set_choices_for_field("ooi_type", ooi_types_choices)


class SelectOOIForm(BaseRockyForm):
    ooi = forms.MultipleChoiceField(
        label=_("Objects"),
        widget=CheckboxTable(
            column_names=("Object", _("Type"), _("Clearance Level"), _("Next scan")),
            column_templates=(
                "partials/hyperlink_ooi_id.html",
                "partials/hyperlink_ooi_type.html",
                "partials/scan_level_indicator.html",
                "partials/ooi_schedule.html",
            ),
        ),
    )

    def __init__(
        self,
        oois: list[tuple[OOI, ScheduleResponse]],
        organization_code: str,
        mandatory_fields: list | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.fields["ooi"].widget.attrs["organization_code"] = organization_code
        if mandatory_fields:
            self.fields["ooi"].widget.attrs["mandatory_fields"] = mandatory_fields
        self.set_choices_for_field("ooi", [self._to_choice(ooi) for ooi in oois])
        if len(self.fields["ooi"].choices) == 1:
            self.fields["ooi"].initial = self.fields["ooi"].choices[0][0]

    @staticmethod
    def _to_choice(ooi_with_schedule: tuple[OOI, ScheduleResponse]) -> tuple[str, Any]:
        ooi, schedule = ooi_with_schedule[0], ooi_with_schedule[1]

        return str(ooi), (ooi, ooi, ooi.scan_profile.level if ooi.scan_profile else 0, schedule)


class SelectOOIFilterForm(BaseRockyForm):
    show_all = forms.NullBooleanField(
        label=_("Show objects that don't meet the Boefjes scan level."),
        widget=forms.CheckboxInput(attrs={"class": "submit-on-click"}),
    )


class PossibleBoefjesFilterForm(BaseRockyForm):
    show_all = forms.NullBooleanField(
        widget=LabeledCheckboxInput(label=_("Show Boefjes that exceed the objects clearance level."), autosubmit=True)
    )


class SetClearanceLevelForm(forms.Form):
    clearance_type = forms.CharField(
        required=True,
        label=_("Clearance type"),
        widget=forms.RadioSelect(
            choices=[("inherited", "Inherited"), ("declared", "Declared")],
            attrs={"class": "radio-choice", "data-choicegroup": "scan_type_selector"},
        ),
        initial="inherited",
    )

    level = forms.IntegerField(
        required=False,
        label=_("Clearance level"),
        help_text=_(
            "All the boefjes with a scan level below or equal to the clearance level will "
            "be allowed to scan this object."
        ),
        error_messages={"level": {"required": _("Please select a clearance level to proceed.")}},
        widget=forms.Select(
            choices=SCAN_LEVEL_CHOICES,
            attrs={"aria-describedby": _("explanation-clearance-level"), "class": "scan_type_selector declared"},
        ),
    )


class MuteFindingForm(forms.Form):
    finding = forms.CharField(widget=forms.HiddenInput(), required=False)
    ooi_type = forms.CharField(widget=forms.HiddenInput(), required=False)
    reason = forms.CharField(widget=forms.Textarea(attrs={"name": "reason", "rows": "3", "cols": "5"}), required=False)
    end_valid_time = forms.DateTimeField(
        label=_("Expires by (UTC)"),
        widget=forms.DateTimeInput(attrs={"name": "end_valid_time", "type": "datetime-local"}),
        required=False,
    )
