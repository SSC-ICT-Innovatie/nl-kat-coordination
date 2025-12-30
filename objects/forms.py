import csv
import io
from typing import Any, cast

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from objects.models import Network, XTDBOrganization
from openkat.forms.upload_csv import UploadCSVForm


def clean_asset_csv(cleaned_data: dict[str, Any], column_name: str) -> None:
    csv_file = cleaned_data.get("csv_file")
    if csv_file:
        try:
            rows = list(csv.reader(io.StringIO(csv_file.read().decode("UTF-8")), delimiter=",", quotechar='"'))
            csv_file.seek(0)

            if not rows:
                raise ValidationError(_("CSV file is empty."))

            for i, row in enumerate(rows, 1):
                if not row or not row[0].strip():
                    continue  # Skip empty rows
                if len(row) > 2:
                    raise ValidationError(
                        _(
                            "Row {row_num} has {col_count} columns. "
                            "Expected 1-2 columns ({column_name}, organization_id)."
                        ).format(row_num=i, col_count=len(row), column_name=column_name)
                    )
        except csv.Error as e:
            raise ValidationError(_("Error parsing CSV: {error}").format(error=str(e)))


class HostnameCSVUploadForm(UploadCSVForm):
    network = forms.ModelChoiceField(
        queryset=Network.objects.all(),
        required=False,
        label=_("Network"),
        help_text=_("Select network for all hostnames. Defaults to 'internet' network."),
    )

    def clean(self):
        cleaned_data = cast("dict[str, Any]", super().clean())
        return clean_asset_csv(cleaned_data, "name")


class IPAddressCSVUploadForm(UploadCSVForm):
    network = forms.ModelChoiceField(
        queryset=Network.objects.all(),
        required=False,
        label=_("Network"),
        help_text=_("Select network for all IP addresses. Defaults to 'internet' network."),
    )

    def clean(self):
        cleaned_data = cast("dict[str, Any]", super().clean())
        return clean_asset_csv(cleaned_data, "address")


class GenericAssetBulkCreateForm(forms.Form):
    assets = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 10, "placeholder": "192.168.1.1\nexample.com\n10.0.0.1\ntest.org"}),
        label=_("IP Addresses or Hostnames"),
        help_text=_("Enter one IP address or hostname per line."),
        required=True,
    )
    network = forms.ModelChoiceField(
        queryset=Network.objects.all(),
        required=False,
        label=_("Network"),
        help_text=_("Select network for all assets. Defaults to 'internet' network."),
    )
    organizations = forms.ModelMultipleChoiceField(
        queryset=XTDBOrganization.objects.all(),
        required=False,
        label=_("Organizations"),
        help_text=_("Select organizations for all assets (optional)."),
        widget=forms.CheckboxSelectMultiple,
    )

    def clean_assets(self):
        assets = self.cleaned_data.get("assets", "")
        lines = [line.strip() for line in assets.splitlines() if line.strip()]

        if not lines:
            raise ValidationError(_("Please provide at least one IP address or hostname."))

        return lines


class GenericAssetCSVUploadForm(UploadCSVForm):
    network = forms.ModelChoiceField(
        queryset=Network.objects.all(),
        required=False,
        label=_("Network"),
        help_text=_("Select default network for all assets. Defaults to 'internet'."),
    )

    def clean(self):
        if (cleaned_data := super().clean()) is None:
            return cleaned_data
        csv_file = cleaned_data.get("csv_file")

        if csv_file:
            csv_data = io.StringIO(csv_file.read().decode("UTF-8"))
            csv_file.seek(0)

            try:
                rows = list(csv.reader(csv_data, delimiter=",", quotechar='"'))

                if not rows:
                    raise ValidationError(_("CSV file is empty."))

                # Column 1: asset (IP or hostname) - required
                # Column 2: scan_level (optional)
                # Column 3: organization id (optional)
                for i, row in enumerate(rows, 1):
                    if not row or not row[0].strip():
                        continue

                    if len(row) > 3:
                        raise ValidationError(
                            _(
                                "Row {num} has {col} columns. Expected 1-3 columns (asset, scan_level, organization)."
                            ).format(num=i, col=len(row))
                        )

            except csv.Error as e:
                raise ValidationError(_("Error parsing CSV: {error}").format(error=str(e)))

        return cleaned_data
