import io
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar
from uuid import uuid4

import yaml
import yaml.composer
import yaml.parser
from account.mixins import OrganizationPermissionRequiredMixin, OrganizationView
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.urls.base import reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic.edit import FormView
from pydantic import ValidationError
from tools.forms.upload_oois import UploadOOIYMLForm

from octopoes.api.models import Declaration
from octopoes.models.types import ALL_TYPES
from rocky.bytes_client import get_bytes_client

YML_CRITERIA = [
    _('All objects should be stored in the "oois" list at the root level.'),
    _("Objects of various types can be included in a single file."),
    _("Each object must begin with class name with exclamation at the beginning"),
    _("It can create an object that has a reference that actually doesn't exist at all!"),
]

BASE_CLS_INFO = [
    _(
        "An example of base OOI class can be IPAddress and it is base for IPAddressV4 or IPAddressV6. "
        "They have different requisites to turn them into one of their child types. "
        "If you use an exported file, you don't have to concern about this."
    ),
    _("IPAddress base type automatically switch to IPAddressV4 or IPAddressV6 according to address field."),
    _("NetBlock base type automatically switch to IPV4NetBlock or IPV6NetBlock according to start_ip field."),
    _("DNSRecord base type automatically switch to proper class according to dns_record_type field."),
    _(
        "WebUrl base type should have netloc field. "
        "According to netloc (Hostname or IPv4Address en IPv6Address) "
        "it will turn into HostnameHTTPURL or IPAddressHTTPURL."
    ),
    _("SubjectAlternativeName base type should have proper fields to define as one of child types."),
]


def extract_yml_examples_in_raw_str():
    result = {}
    example_yml_file_path = Path.joinpath(Path(os.path.dirname(__file__)), "upload_yml_examples.yml")
    with open(example_yml_file_path, encoding="utf-8") as file:
        raw_str_ooi = ""
        current_ooi_name = ""
        current_examples = []
        first_obj = True
        for line in file:
            l_stripped_line = line.lstrip()
            if l_stripped_line.startswith("#") or l_stripped_line.startswith("oois:") or line.strip() == "":
                continue
            if l_stripped_line.startswith("- !"):
                ooi_name = line.strip()[3:]
                if first_obj:
                    first_obj = False
                    current_ooi_name = ooi_name
                else:
                    if ooi_name == current_ooi_name:
                        current_examples.append(raw_str_ooi)
                        raw_str_ooi = ""
                    else:
                        current_examples.append(raw_str_ooi)
                        result[current_ooi_name] = current_examples
                        current_examples = []
                        current_ooi_name = ooi_name
                        raw_str_ooi = ""
            raw_str_ooi += line.rstrip() + "\n"
        current_examples.append(raw_str_ooi)
        result[current_ooi_name] = current_examples
    return result


YML_EXAMPLES = extract_yml_examples_in_raw_str()

# Some OOI types cannot instantiated
banned_ooi_classes = [
    "DNSSPFMechanism",
    "BaseReport",
    "ReportData",
    "AssetReport",
    "Report",
    "HydratedReport",
    "ReportRecipe",
    "CWEFindingType",
    "CVEFindingType",
    "CAPECFindingType",
    "FindingType",
    "Finding",
    "KATFindingType",
    "RetireJSFindingType",
    "SnykFindingType",
    "OOI",
]


class UploadYML(OrganizationPermissionRequiredMixin, OrganizationView, FormView):
    template_name = "upload_yml.html"
    form_class = UploadOOIYMLForm
    permission_required = "tools.can_scan_organization"
    # ooi_types: ClassVar[dict[str, Any]] = {
    #     ooi_type: {"type": OOI_TYPES[ooi_type]} for ooi_type in OOI_TYPES if ooi_type not in banned_ooi_classes
    # }
    ooi_types: ClassVar[dict[str, Any]] = {
        ooi_type.__name__: {"type": ooi_type} for ooi_type in ALL_TYPES if ooi_type.__name__ not in banned_ooi_classes
    }

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy("ooi_list", kwargs={"organization_code": self.organization.code})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"url": reverse("ooi_list", kwargs={"organization_code": self.organization.code}), "text": _("Objects")},
            {
                "url": reverse("upload_yml", kwargs={"organization_code": self.organization.code}),
                "text": _("Upload YAML"),
            },
        ]
        context["criteria"] = YML_CRITERIA
        context["base_ooi_types"] = BASE_CLS_INFO
        context["examples"] = YML_EXAMPLES
        # filter base ooi classes from the "creatable list"
        ooi_types_for_contex = list(self.ooi_types.keys())
        context["ooi_types"] = sorted(ooi_types_for_contex)
        return context

    def form_valid(self, form):
        if not self.process_yml(form):
            return redirect("upload_yml", organization_code=self.organization.code)
        return super().form_valid(form)

    def add_error_notification(self, error_message):
        messages.add_message(self.request, messages.ERROR, error_message)
        return False

    def add_success_notification(self, success_message):
        messages.add_message(self.request, messages.SUCCESS, success_message)
        return True

    def read_file(self, yml_file):
        try:
            bytes_from_file = yml_file.read()
            return bytes_from_file
        except UnicodeDecodeError:
            self.add_error_notification("File could not be decoded)")

    def process_yml(self, form):
        yml_file = form.cleaned_data["yml_file"]
        yml_raw_data = self.read_file(yml_file)
        if not yml_raw_data:
            return
        task_id = uuid4()
        get_bytes_client(self.organization.code).add_manual_proof(
            task_id, yml_raw_data, manual_mime_types={"manual/yml"}
        )
        yml_data = io.StringIO(yml_raw_data.decode("UTF-8"))
        try:
            refs_and_oois = yaml.safe_load(yml_data)
        except yaml.composer.ComposerError as err:
            return self.add_error_notification(f"Corrupted yaml file imported. Error: {err}")
        except yaml.parser.ParserError as err:
            return self.add_error_notification(f"Corrupted yaml file imported. Error: {err}")
        except ValidationError as err:
            return self.add_error_notification(f"Validation error: {err}")
        oois_from_yaml = refs_and_oois["oois"]

        for ooi in oois_from_yaml:
            self.octopoes_api_connector.save_declaration(
                Declaration(ooi=ooi, valid_time=datetime.now(timezone.utc), task_id=task_id)
            )
            if ooi.scan_profile is not None:
                self.raise_clearance_level(ooi.reference, ooi.scan_profile.level)
        self.add_success_notification(_("Object(s) successfully added."))
