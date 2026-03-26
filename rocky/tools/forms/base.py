import contextlib
from datetime import datetime, timezone
from typing import Any

from django import forms
from django.forms import Widget
from django.utils.translation import gettext_lazy as _

from tools.forms.settings import OBSERVED_AT_HELP_TEXT, Choices, ChoicesGroups


class BaseRockyModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label_suffix = ""  # Removes : as label suffix


class BaseRockyForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label_suffix = ""  # Removes : as label suffix

    def set_choices_for_field(self, field: str, choices: Choices | ChoicesGroups) -> None:
        if field in self.fields:
            self.fields[field].choices = choices

    def set_choices_for_widget(self, field: str, choices: Choices | ChoicesGroups) -> None:
        self.fields[field].widget.choices = choices

    def set_required_options_for_widget(self, field: str, required_options: list[str]) -> None:
        """For multiselect widgets, set the required options."""
        self.fields[field].widget.required_options = required_options


class DateInput(forms.DateInput):
    input_type = "date"


class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"


class DataListInput(forms.Select):
    input_type = "text"
    template_name = "forms/widgets/datalist.html"

    def __init__(self, attrs=None, choices=()):
        super().__init__(attrs)
        self.choices = list(choices)

    def format_value(self, value):
        """Return selected value as string."""
        if value is None:
            return ""
        return str(value)


class ObservedAtForm(BaseRockyForm):
    observed_at = forms.DateField(
        label=_("Date"), widget=DateInput(format="%Y-%m-%d"), required=False, help_text=OBSERVED_AT_HELP_TEXT
    )

    def clean_observed_at(self):
        observed_at = self.cleaned_data["observed_at"]
        now = datetime.now(tz=timezone.utc)
        if observed_at and observed_at > now.date():
            raise forms.ValidationError(_("The selected date is in the future. Please select a different date."))
        return observed_at


class LabeledCheckboxInput(forms.CheckboxInput):
    template_name = "forms/widgets/checkbox_option.html"

    def __init__(self, label: str = "", autosubmit: bool = False):
        super().__init__()
        self.label = label
        self.autosubmit = autosubmit

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["wrap_label"] = True
        context["widget"]["label"] = self.label
        context["widget"]["attrs"]["class"] = "submit-on-click"
        return context


class CheckboxGroup(forms.CheckboxSelectMultiple):
    input_type = "checkbox"
    template_name = "forms/widgets/checkbox_group_columns.html"
    option_template_name = "forms/widgets/checkbox_option.html"
    required_options: list[str]
    wrap_label = True

    def __init__(self, required_options: list[str] | None = None, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.required_options = required_options or []

    def get_context(self, name: str, value: Any, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        return context

    def create_option(self, *arg: Any, **kwargs: Any) -> dict[str, Any]:
        option = super().create_option(*arg, **kwargs)
        option["wrap_label"] = self.wrap_label
        option["attrs"]["checked"] = self.is_required_option(option["value"])
        option["attrs"]["required"] = self.is_required_option(option["value"])
        return option

    def is_required_option(self, value: str) -> bool:
        return value in self.required_options


class CheckboxTable(Widget):
    input_type = "checkbox"
    template_name = "forms/widgets/checkbox_group_table.html"
    checkbox_template_name = "forms/widgets/checkbox_option.html"
    checked_attribute = {"checked": True}
    option_inherits_attrs = False
    add_id_index = False
    allow_multiple_selected = True
    wrap_label = False

    def __init__(self, attrs=None, column_names=(), choices=(), column_templates=()):
        super().__init__(attrs)
        self.choices = choices
        self.column_names = column_names
        self.column_templates = column_templates

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)

        context["widget"]["options"] = []
        for index, (choice_value, choice_label) in enumerate(self.choices):
            selected = str(choice_value) in value if value is not None else False
            context["widget"]["options"].append(
                self.create_option(name, choice_value, choice_label, selected, index, attrs=attrs)
            )

        context["widget"]["column_names"] = self.column_names
        context["widget"]["column_templates"] = self.column_templates
        return context

    def id_for_label(self, id_, index="0"):
        """
        Use an incremented id for each option where the main widget
        references the zero index.
        """
        if id_ and self.add_id_index:
            id_ = f"{id_}_{index}"
        return id_

    def create_option(self, name, value, label, selected, index, attrs=None):
        index = str(index)
        if attrs is None:
            attrs = {}
        option_attrs = self.build_attrs(self.attrs, attrs) if self.option_inherits_attrs else {}
        if selected:
            option_attrs.update(self.checked_attribute)
        if "id" in option_attrs:
            option_attrs["id"] = self.id_for_label(option_attrs["id"], index)
        return {
            "name": name,
            "value": value,
            "label": label,
            "selected": selected,
            "index": index,
            "attrs": option_attrs,
            "type": self.input_type,
            "template_name": self.checkbox_template_name,
            "wrap_label": self.wrap_label,
        }

    def value_from_datadict(self, data, files, name):
        del files
        getter = data.get
        if self.allow_multiple_selected:
            with contextlib.suppress(AttributeError):
                getter = data.getlist

        return getter(name)

    def format_value(self, value):
        """Return selected values as a list."""
        if value is None and self.allow_multiple_selected:
            return []
        if not isinstance(value, tuple | list):
            value = [value]
        return [str(v) if v is not None else "" for v in value]
