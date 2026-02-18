from datetime import datetime, timezone
from uuid import uuid4

from django.forms import Form
from django.shortcuts import redirect
from django.urls.base import reverse
from django.utils.translation import gettext_lazy as _
from tools.forms.finding_type import FindingAddForm
from tools.view_helpers import get_ooi_url

from octopoes.api.models import Declaration
from octopoes.models import Reference
from octopoes.models.ooi.findings import (
    CAPECFindingType,
    CVEFindingType,
    CWEFindingType,
    Finding,
    FindingType,
    KATFindingType,
    RetireJSFindingType,
    SnykFindingType,
)
from octopoes.models.types import OOI_TYPES
from rocky.bytes_client import BytesClient, get_bytes_client
from rocky.views.ooi_view import BaseOOIFormView

FINDING_TYPES_PREFIXES = {
    "CVE": CVEFindingType,
    "SNYK": SnykFindingType,
    "CWE": CWEFindingType,
    "CAPEC": CAPECFindingType,
    "RetireJS": RetireJSFindingType,
    "KAT": KATFindingType,
}


def get_finding_type_from_id(finding_type_id: str) -> FindingType:
    finding_type_id = finding_type_id.upper()

    prefix = finding_type_id.upper().split("-")[0]
    if prefix in FINDING_TYPES_PREFIXES:
        return FINDING_TYPES_PREFIXES[prefix](id=finding_type_id)
    else:
        raise ValueError("Invalid finding type prefix")


class FindingAddView(BaseOOIFormView):
    template_name = "findings/finding_add.html"
    form_class = FindingAddForm

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.initial = {"ooi_id": request.GET.get("ooi_id")}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["breadcrumbs"] = [
            {"url": reverse("finding_list", kwargs={"organization_code": self.organization.code}), "text": "Findings"},
            {
                "url": reverse("finding_add", kwargs={"organization_code": self.organization.code}),
                "text": _("Add finding"),
            },
        ]

        return context

    def get_form_kwargs(self):
        kwargs = {"connector": self.octopoes_api_connector, "ooi_list": self.get_ooi_options()}
        kwargs.update(super().get_form_kwargs())

        if "ooi_class" in kwargs:
            del kwargs["ooi_class"]

        return kwargs

    def get_form(self, form_class: type[Form] | None = None) -> FindingAddForm:
        if form_class is None:
            form_class = self.get_form_class()

        return form_class(**self.get_form_kwargs())

    def form_valid(self, form):
        form_data = form.cleaned_data

        ooi_id = form_data["ooi_id"]

        s: str = form_data["finding_type_ids"]
        finding_type_ids = s.replace(",", "\n").splitlines()
        finding_type_ids = [
            x.strip()
            for x in finding_type_ids
            if x.strip().startswith(("KAT-", "CVE-", "CWE-", "CAPEC-", "RetireJS-", "SNYK-"))
        ]

        observed_at = datetime.combine(form_data.get("date"), datetime.min.time(), tzinfo=timezone.utc)

        # Create finding for each finding type
        ooi_ref = Reference.from_str(ooi_id)

        proof = []  # Collect as much data as possible in a single proof

        task_id = uuid4()
        for f_id in finding_type_ids:
            finding_type = get_finding_type_from_id(f_id)
            finding = Finding(
                ooi=ooi_ref,
                finding_type=finding_type.reference,
                proof=form_data.get("proof"),
                description=form_data.get("description"),
                reproduce=form_data.get("reproduce"),
            )
            proof.append(Declaration(ooi=finding, valid_time=observed_at, task_id=str(task_id)))
            proof.append(Declaration(ooi=finding_type, valid_time=observed_at, task_id=str(task_id)))

        get_bytes_client(self.organization.code).add_manual_proof(task_id, BytesClient.raw_from_declarations(proof))

        for declaration in proof:
            self.octopoes_api_connector.save_declaration(declaration)

        return redirect(get_ooi_url("ooi_detail", ooi_id, self.organization.code))

    def get_ooi_options(self) -> list[tuple[str, str]]:
        # Query to render form options
        ooi_set = set(OOI_TYPES.values()).difference({Finding, FindingType})
        objects = self.octopoes_api_connector.list_objects(ooi_set, valid_time=datetime.now(timezone.utc)).items

        # generate options
        options = [(o.primary_key, o.get_ooi_type()) for o in objects]

        return options
