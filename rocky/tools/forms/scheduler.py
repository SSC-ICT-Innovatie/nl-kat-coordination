from datetime import datetime, timezone

from django import forms
from django.utils.translation import gettext_lazy as _

from tools.forms.base import DateInput


class TaskFilterForm(forms.Form):
    min_created_at = forms.DateField(label=_("From"), widget=DateInput(format="%Y-%m-%d"), required=False)
    max_created_at = forms.DateField(label=_("To"), widget=DateInput(format="%Y-%m-%d"), required=False)
    status = forms.ChoiceField(
        choices=(
            ("", _("All")),
            ("cancelled", _("Cancelled")),
            ("completed", _("Completed")),
            ("dispatched", _("Dispatched")),
            ("failed", _("Failed")),
            ("pending", _("Pending")),
            ("queued", _("Queued")),
            ("running", _("Running")),
        ),
        required=False,
    )
    ooi_search = forms.CharField(
        label=_("Search (in OOI)"),
        widget=forms.TextInput(attrs={"placeholder": _("Search by object name")}),
        required=False,
    )
    ooi_id = forms.CharField(
        label=_("Input OOI"), widget=forms.TextInput(attrs={"placeholder": _("Select specific object")}), required=False
    )
    plugin_id = forms.CharField(
        label=_("Plugin"), widget=forms.TextInput(attrs={"placeholder": _("Search by plugin")}), required=False
    )
    task_id = forms.CharField(
        label=_("Task id"), widget=forms.TextInput(attrs={"placeholder": _("Search by task ID")}), required=False
    )

    organizations = forms.MultipleChoiceField(choices=(), required=False)

    def __init__(self, *args, organizations=None, **kwargs):
        super().__init__(*args, **kwargs)

        if organizations is not None:
            choices = [("", _("All"))]
            choices.extend([(org, org) for org in organizations])
            self.fields["organizations"].choices = choices

    def clean(self):
        cleaned_data = super().clean()

        min_created_at = cleaned_data.get("min_created_at")
        max_created_at = cleaned_data.get("max_created_at")

        date_message = _("The selected date (%s) is in the future. Please select a different date.")

        now = datetime.now(tz=timezone.utc)

        if min_created_at is not None and min_created_at > now.date():
            self.add_error("min_created_at", date_message % _("'from'"))

        if max_created_at is not None and max_created_at > now.date():
            self.add_error("max_created_at", date_message % _("'to'"))

        # swap dates around if user swapped them by accident.
        if min_created_at is not None and max_created_at is not None and min_created_at > max_created_at:
            cleaned_data["max_created_at"] = min_created_at
            cleaned_data["min_created_at"] = max_created_at

        return cleaned_data


class OrganizationTaskFilterForm(TaskFilterForm):
    organizations = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class OOIDetailTaskFilterForm(OrganizationTaskFilterForm):
    """
    Task filter at OOI detail to pass observed_at and ooi_id values.
    """

    observed_at = forms.CharField(widget=forms.HiddenInput(), required=False)
    ooi_id = forms.CharField(widget=forms.HiddenInput(), required=False)

    # No need to search for OOI if you are already at the OOI detail page.
    ooi_search = None
