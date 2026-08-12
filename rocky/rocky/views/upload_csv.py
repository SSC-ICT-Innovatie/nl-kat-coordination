import csv
import io
from datetime import datetime, timezone
from typing import Any, ClassVar
from uuid import uuid4

from account.mixins import OrganizationPermissionRequiredMixin, OrganizationView
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.urls.base import reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic.edit import FormView
from httpx import HTTPError
from pydantic import ValidationError
from tools.forms.upload_csv import CSV_ERRORS
from tools.forms.upload_oois import UploadOOICSVForm

from octopoes.api.models import Declaration
from octopoes.models import OOI, Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, Network
from octopoes.models.ooi.web import URL

CSV_CRITERIA = [
    _("Add column titles. Followed by each object on a new line."),
    _(
        "For URL object type, a column 'raw' with URL values is required, starting with http:// or https://, "
        "optionally a second column 'network' is supported "
    ),
    _(
        "For Hostname object type, a column with 'name' values is required, optionally a second column 'network' "
        "is supported "
    ),
    _(
        "For IPAddressV4 and IPAddressV6 object types, a column of 'address' is required, optionally a second column "
        "'network' is supported "
    ),
    _(
        "Clearance levels can be controlled by a column 'clearance' taking numerical values 0, 1, 2, 3, and 4 for "
        "the corresponding clearance level (other values are ignored) "
    ),
]

CLEARANCE_VALUES = ["0", "1", "2", "3", "4"]


class UploadCSV(OrganizationPermissionRequiredMixin, OrganizationView, FormView):
    template_name = "upload_csv.html"
    form_class = UploadOOICSVForm
    permission_required = "tools.can_scan_organization"
    reference_cache: dict[str, Any] = {"Network": {"internet": Network(name="internet")}}
    ooi_types: ClassVar[dict[str, Any]] = {
        "Hostname": {"type": Hostname},
        "URL": {"type": URL},
        "Network": {"type": Network, "default": "internet", "argument": "name"},
        "IPAddressV4": {"type": IPAddressV4},
        "IPAddressV6": {"type": IPAddressV6},
    }
    skip_properties = ("object_type", "scan_profile", "primary_key")

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        if not self.organization:
            self.add_error_notification(CSV_ERRORS["no_org"])

    def get_success_url(self):
        return reverse_lazy("ooi_list", kwargs={"organization_code": self.organization.code})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"url": reverse("ooi_list", kwargs={"organization_code": self.organization.code}), "text": _("Objects")},
            {
                "url": reverse("upload_csv", kwargs={"organization_code": self.organization.code}),
                "text": _("Upload CSV"),
            },
        ]
        context["criteria"] = CSV_CRITERIA
        return context

    def get_or_create_reference(self, ooi_type_name: str, value: str | None) -> OOI:
        ooi_type_name = next(filter(lambda x: x.casefold() == ooi_type_name.casefold(), self.ooi_types.keys()))

        # get from cache
        cache = self.reference_cache.setdefault(ooi_type_name, {})
        if value in cache:
            return cache[value]

        ooi_type = self.ooi_types[ooi_type_name]["type"]

        # set default value if any
        if value is None:
            value = self.ooi_types[ooi_type_name].get("default")

        # create the ooi
        kwargs = {self.ooi_types[ooi_type_name]["argument"]: value}
        ooi = ooi_type(**kwargs)
        cache[value] = ooi

        return ooi

    def get_ooi_from_csv(self, ooi_type_name: str, values: dict[str, str]) -> tuple[OOI, int | None, list[Declaration]]:
        key = "clearance"
        level = int(values[key]) if key in values and values[key] in CLEARANCE_VALUES else None
        ooi_type = self.ooi_types[ooi_type_name]["type"]
        ooi_fields = [
            (field, model_field.annotation == Reference, model_field.is_required())
            for field, model_field in ooi_type.model_fields.items()
            if field not in self.skip_properties
        ]

        kwargs: dict[str, Any] = {}
        declarations = []
        for field, is_reference, required in ooi_fields:
            if is_reference and required:
                try:
                    referenced_ooi = self.get_or_create_reference(field, values.get(field))
                    declarations.append(Declaration(ooi=referenced_ooi, valid_time=datetime.now(timezone.utc)))
                    kwargs[field] = referenced_ooi.reference
                except IndexError:
                    if required:
                        raise IndexError(
                            f"Required referenced primary-key field '{field}' not set "
                            f"and no default present for Type '{ooi_type_name}'."
                        )
                    else:
                        kwargs[field] = None
            else:
                kwargs[field] = values.get(field)

        return ooi_type(**kwargs), level, declarations

    def form_valid(self, form):
        if not self.process_csv(form):
            return redirect("upload_csv", organization_code=self.organization.code)
        return super().form_valid(form)

    def add_error_notification(self, error_message):
        messages.add_message(self.request, messages.ERROR, error_message)
        return False

    def add_success_notification(self, success_message):
        messages.add_message(self.request, messages.SUCCESS, success_message)
        return True

    def process_csv(self, form):
        object_type = form.cleaned_data["object_type"]
        csv_file = form.cleaned_data["csv_file"]

        csv_raw_data = csv_file.read()

        task_id = uuid4()
        self.bytes_client.add_manual_proof(task_id, csv_raw_data, manual_mime_types={"manual/csv"})

        csv_data = io.StringIO(csv_raw_data.decode("UTF-8"))
        rows_with_error = []
        oois = []
        try:
            for row_number, row in enumerate(csv.DictReader(csv_data, delimiter=",", quotechar='"'), start=1):
                if not row:
                    continue  # skip empty lines
                try:
                    ooi, level, declarations = self.get_ooi_from_csv(object_type, row)
                    if declarations:
                        oois.extend(declarations)
                    oois.append(Declaration(ooi=ooi, valid_time=datetime.now(timezone.utc), task_id=task_id))
                    if isinstance(level, int):
                        self.raise_clearance_level(ooi.reference, level)
                except ValidationError:
                    rows_with_error.append(row_number)

            if rows_with_error:
                message = _("Object(s) could not be created for row number(s): ") + ", ".join(map(str, rows_with_error))
                return self.add_error_notification(message)

            self.add_success_notification(_("Object(s) successfully added."))
        except (csv.Error, IndexError):
            return self.add_error_notification(CSV_ERRORS["csv_error"])

        try:
            self.octopoes_api_connector.save_many_declarations(oois, sync=True)
        except HTTPError:
            return self.add_error_notification("Failed to save data from the CSV")
