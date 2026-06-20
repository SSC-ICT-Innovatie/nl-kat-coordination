from django import forms
from django.utils.translation import gettext as _

YML_ERRORS = {
    "only_yml": _("Only YAML file supported"),
    "decoding": _("File could not be decoded"),
    "no_file": _("No file selected"),
    "empty_file": _("The uploaded file is empty."),
    "bad_ooi_type": _("OOI Type in YAML does not meet the criteria."),
    "yml_error": _("An error has occurred during the parsing of the yml file:"),
}


class UploadYMLForm(forms.Form):
    yml_file = forms.FileField(
        label=_("Upload YAML file"), help_text=_("Only accepts YAML file."), allow_empty_file=False
    )

    def clean_yml_file(self):
        yml_file = self.cleaned_data["yml_file"]
        if not (yml_file.name.endswith(".yml") or yml_file.name.endswith("yaml")):
            self.add_error("yml_file", YML_ERRORS["only_yml"])
        return yml_file
