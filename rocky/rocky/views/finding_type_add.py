from datetime import datetime, timezone
from uuid import uuid4

from account.mixins import OrganizationView
from django.shortcuts import redirect
from django.urls.base import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from tools.forms.finding_type import FindingTypeAddForm
from tools.models import OOIInformation
from tools.view_helpers import get_ooi_url

from octopoes.api.models import Declaration
from octopoes.models.ooi.findings import KATFindingType
from rocky.bytes_client import BytesClient


class FindingTypeAddView(OrganizationView, FormView):
    template_name = "finding_type_add.html"
    form_class = FindingTypeAddForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["breadcrumbs"] = [
            {
                "url": reverse("finding_list", kwargs={"organization_code": self.organization.code}),
                "text": _("Findings"),
            },
            {
                "url": reverse("finding_type_add", kwargs={"organization_code": self.organization.code}),
                "text": _("Add finding type"),
            },
        ]

        return context

    def form_valid(self, form):
        self.api_connector = self.octopoes_api_connector
        form_data = form.cleaned_data
        # set data
        finding_type = KATFindingType(id=form_data["id"])
        info, created = OOIInformation.objects.get_or_create(id=f'KATFindingType|{form_data["id"]}')
        info.data = {
            "title": form_data["title"],
            "description": form_data["description"],
            "risk": form_data["risk"],
            "solution": form_data["solution"],
            "references": form_data["references"],
            "impact_description": form_data["impact_description"],
            "solution_chance": form_data["solution_chance"],
            "solution_impact": form_data["solution_impact"],
            "solution_effort": form_data["solution_effort"],
        }

        info.save()

        task_id = uuid4()
        declaration = Declaration(ooi=finding_type, valid_time=datetime.now(timezone.utc), task_id=str(task_id))

        self.bytes_client.add_manual_proof(task_id, BytesClient.raw_from_declarations([declaration]))
        self.api_connector.save_declaration(declaration, sync=True)

        return redirect(get_ooi_url("ooi_detail", finding_type.primary_key, self.organization.code))
