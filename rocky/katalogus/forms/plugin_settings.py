from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _
from jsonschema.validators import Draft202012Validator

FIELD_TYPES = {"string": forms.CharField, "integer": forms.IntegerField, "enum": forms.Select}
MAX_SETTINGS_VALUE_LENGTH = 128


class PluginSchemaForm(forms.Form):
    """This Form takes a plugin schema and turn all settings of schema into form fields."""

    error_messages = {"required": _("This field is required.")}

    def __init__(self, plugin_schema: dict, values: dict, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.plugin_schema = plugin_schema
        self.values = values
        self.populate_fields()

    def populate_fields(self):
        for field_name, field_props in self.plugin_schema["properties"].items():
            kwargs = {
                "required": "required" in self.plugin_schema and field_name in self.plugin_schema["required"],
                "label": field_props.get("title", field_name),
                "help_text": _(field_props.get("description", "")),
                "error_messages": self.error_messages,
            }
            if field_props["type"] == "string":
                kwargs["max_length"] = min(
                    MAX_SETTINGS_VALUE_LENGTH, field_props.get("maxLength", MAX_SETTINGS_VALUE_LENGTH)
                )

            if field_name in self.values:
                kwargs["initial"] = self.values[field_name]

            field_type = FIELD_TYPES[field_props["type"]]
            self.fields[field_name] = field_type(**kwargs)

    def clean(self):
        cleaned_data = super().clean()

        # The form assigns "" and in some scenario's null to all unfilled (optional) fields
        cleaned_data = {
            key: value
            for key, value in cleaned_data.items()
            if value is not None and value != ""  # noqa: PLC1901
        }

        validator = Draft202012Validator(self.plugin_schema)

        if not validator.is_valid(cleaned_data):
            for error in validator.iter_errors(cleaned_data):
                self.add_error(None, error.message)

        return cleaned_data
