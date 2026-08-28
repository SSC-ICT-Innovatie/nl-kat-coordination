from datetime import datetime, timezone

from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models import Reference
from octopoes.models.exception import ObjectNotFoundException
from tools.forms.base import BaseRockyForm, DataListInput, DateTimeInput
from tools.forms.settings import RAW_FILE_DATETIME_HELP_TEXT


class UploadRawForm(BaseRockyForm):
    mime_types = forms.CharField(
        label=_("Mime types"),
        help_text=mark_safe(
            _(
                '<p>Add a set of mime types, separated by commas, for example:</p><p><i>"text/html, image/jpeg"</i> or '
                '<i>"boefje/dns-records"</i>.</p><p>Mime types are used to match the correct normalizer to a raw file. '
                'When the mime type "boefje/dns-records" is added, the normalizer expects the raw file to contain dns '
                "scan information.</p>"
            )
        ),
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "text/html, image/jpeg, ..."}),
    )
    raw_file = forms.FileField(label=_("Upload raw file"), allow_empty_file=False, required=True)

    ooi_id = forms.CharField(
        label=_("Input or Scan OOI"),
        required=True,
        widget=DataListInput(
            attrs={"placeholder": _("Click to select one of the available options, or type one yourself")}
        ),
    )

    date = forms.DateTimeField(
        label=_("Date/Time (UTC)"), widget=DateTimeInput(format="%Y-%m-%dT%H:%M"), help_text=RAW_FILE_DATETIME_HELP_TEXT
    )

    def __init__(self, connector: OctopoesAPIConnector, ooi_list: list[tuple[str, str]], *args, **kwargs):
        observed_at = kwargs.pop("observed_at", None)
        super().__init__(*args, **kwargs)
        self.octopoes_connector = connector
        self.set_choices_for_widget("ooi_id", ooi_list)

        if observed_at:
            try:
                parsed_date = (
                    datetime.strptime(observed_at, "%Y-%m-%d").replace(tzinfo=timezone.utc).replace(hour=23, minute=59)
                )
                self.fields["date"].initial = parsed_date
            except ValueError:
                self.fields["date"].initial = datetime.now(tz=timezone.utc)
        else:
            self.fields["date"].initial = datetime.now(tz=timezone.utc)

    def clean_mime_types(self) -> set[str]:
        mime_types = self.cleaned_data["mime_types"]

        return {mime_type.strip() for mime_type in mime_types.split(",") if mime_type.strip()}

    def clean(self):
        cleaned_data = super().clean()

        date = self.cleaned_data["date"]
        ooi_id = self.data["ooi_id"]

        # date should not be in the future
        if date > datetime.now(tz=timezone.utc):
            self.add_error("date", _("Doc! I'm from the future, I'm here to take you back!"))

        try:
            cleaned_data["ooi"] = self.octopoes_connector.get(Reference.from_str(ooi_id), date)
        except ObjectNotFoundException:
            self.add_error("ooi_id", _("OOI doesn't exist, try another valid time"))

        return cleaned_data
