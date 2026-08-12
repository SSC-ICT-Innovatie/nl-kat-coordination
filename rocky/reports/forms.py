from datetime import datetime, timezone
from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _
from tools.forms.base import BaseRockyForm, DateInput

from reports.report_types.definitions import Report


class OOITypeMultiCheckboxForReportForm(BaseRockyForm):
    ooi_type = forms.MultipleChoiceField(
        label=_("Filter by OOI types"), required=False, widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, ooi_types: list[str], *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.fields["ooi_type"].choices = ((ooi_type, ooi_type) for ooi_type in ooi_types)


class ReportTypeMultiselectForm(BaseRockyForm):
    report_type = forms.MultipleChoiceField(
        label=_("Report types"), required=False, widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, report_types: set[Report], *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        report_types_choices = ((report_type.id, report_type.name) for report_type in report_types)
        self.fields["report_type"].choices = report_types_choices


class ReportScheduleStartDateChoiceForm(BaseRockyForm):
    choose_date = forms.ChoiceField(
        label="",
        required=False,
        widget=forms.RadioSelect(attrs={"class": "submit-on-click"}),
        choices=(("today", _("Today")), ("schedule", _("Different date"))),
        initial="today",
    )


class ReportRecurrenceChoiceForm(BaseRockyForm):
    choose_recurrence = forms.ChoiceField(
        label="",
        required=False,
        widget=forms.RadioSelect(attrs={"class": "submit-on-click"}),
        choices=(("once", _("No, just once")), ("repeat", _("Yes, repeat"))),
        initial="once",
    )


class ReportScheduleStartDateForm(BaseRockyForm):
    start_date = forms.DateField(
        label=_("Start date"),
        widget=DateInput(format="%Y-%m-%d"),
        initial=lambda: datetime.now(tz=timezone.utc).date(),
        required=True,
        input_formats=["%Y-%m-%d"],
    )

    start_time = forms.TimeField(
        label=_("Start time (UTC)"),
        widget=forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
        initial=lambda: datetime.now(tz=timezone.utc).time(),
        required=True,
        input_formats=["%H:%M"],
    )

    recurrence = forms.ChoiceField(
        label=_("Recurrence"),
        required=True,
        widget=forms.Select(attrs={"form": "generate_report"}),
        choices=[
            ("once", _("No recurrence, just once")),
            ("daily", _("Daily")),
            ("weekly", _("Weekly")),
            ("monthly", _("Monthly")),
            ("yearly", _("Yearly")),
        ],
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        start_time = cleaned_data.get("start_time")

        if start_date and start_time:
            start_datetime = datetime.combine(start_date, start_time)
            cleaned_data["start_datetime"] = start_datetime

        return cleaned_data


class CustomReportScheduleForm(BaseRockyForm):
    start_date = forms.DateField(
        label=_("Start date"),
        widget=DateInput(format="%Y-%m-%d"),
        initial=lambda: datetime.now(tz=timezone.utc).date(),
        required=False,
    )
    repeating_number = forms.IntegerField(initial=1, required=False, min_value=1, max_value=100)
    repeating_term = forms.ChoiceField(
        widget=forms.Select,
        choices=[("day", _("day")), ("week", _("week")), ("month", _("month")), ("year", _("year"))],
    )
    on_weekdays = forms.ChoiceField(
        widget=forms.RadioSelect,
        choices=[
            ("monday", "M"),
            ("tuesday", "T"),
            ("wednesday", "W"),
            ("thursday", "T"),
            ("friday", "F"),
            ("saturday", "S"),
            ("sunday", "S"),
        ],
    )
    recurrence_ends = forms.ChoiceField(
        widget=forms.RadioSelect,
        choices=[
            ("never", _("Never")),
            ("on", _("On")),  # user choses a specific date
            ("after", _("After")),  # after how many occurrences? Shows drop down with occurrences
        ],
    )

    end_date = forms.DateField(
        label=_(""), widget=forms.HiddenInput(), initial=lambda: datetime.now(tz=timezone.utc).date(), required=False
    )


class ReportNameForm(BaseRockyForm):
    report_name = forms.CharField(
        label=_("Report name format"), required=True, initial="${report_type} for ${oois_count} objects"
    )
