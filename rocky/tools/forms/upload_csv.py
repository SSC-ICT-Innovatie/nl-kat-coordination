from django import forms
from django.utils.translation import gettext as _

CSV_ERRORS = {
    "only_csv": _("Only CSV file supported"),
    "decoding": _("File could not be decoded"),
    "no_file": _("No file selected"),
    "empty_file": _("The uploaded file is empty."),
    "bad_columns": _("The number of columns do not meet the requirements."),
    "bad_ooi_type": _("OOI Type in CSV does not meet the criteria."),
    "csv_error": _("An error has occurred during the parsing of the csv file:"),
}


class UploadCSVForm(forms.Form):
    csv_file = forms.FileField(
        label=_("Upload CSV file"), help_text=_("Only accepts CSV file."), allow_empty_file=False
    )

    def clean_csv_file(self):
        csv_file = self.cleaned_data["csv_file"]
        if not csv_file.name.endswith(".csv"):
            self.add_error("csv_file", CSV_ERRORS["only_csv"])
        try:
            csv_file.read().decode("UTF-8")
            csv_file.seek(0)  # set cursor back at the beginning of line
        except UnicodeDecodeError:
            self.add_error("csv_file", CSV_ERRORS["decoding"])
        return csv_file
