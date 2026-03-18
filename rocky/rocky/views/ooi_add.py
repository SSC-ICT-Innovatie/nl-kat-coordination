from account.mixins import OrganizationView
from django.http import Http404
from django.shortcuts import redirect
from django.urls.base import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from tools.ooi_helpers import OOI_TYPES_WITHOUT_FINDINGS
from tools.view_helpers import existing_ooi_type

from octopoes.models import OOI
from octopoes.models.ooi.monitoring import Incident
from octopoes.models.ooi.question import Question
from octopoes.models.ooi.reports import AssetReport, BaseReport, HydratedReport, Report, ReportData
from octopoes.models.ooi.web import ImageMetadata
from octopoes.models.types import type_by_name
from rocky.views.ooi_view import BaseOOIFormView

EXCLUDE_OOI_TYPES = [
    ooi_type.get_object_type()
    for ooi_type in [Question, Incident, ImageMetadata, Report, ReportData, BaseReport, AssetReport, HydratedReport]
]


def ooi_type_input_choices():
    ooi_types = [ooi_type for ooi_type in OOI_TYPES_WITHOUT_FINDINGS if ooi_type not in EXCLUDE_OOI_TYPES]
    ooi_types.sort()
    return [{"value": ooi_type, "text": ooi_type} for ooi_type in ooi_types]


class OOIAddTypeSelectView(OrganizationView, TemplateView):
    template_name = "oois/ooi_add_type_select.html"

    def get(self, request, *args, **kwargs):
        if "add_ooi_type" in request.GET and existing_ooi_type(request.GET["add_ooi_type"]):
            return redirect(
                reverse(
                    "ooi_add",
                    kwargs={"organization_code": self.organization.code, "ooi_type": request.GET["add_ooi_type"]},
                )
            )

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["ooi_types"] = ooi_type_input_choices()
        context["breadcrumbs"] = [
            {"url": reverse("ooi_list", kwargs={"organization_code": self.organization.code}), "text": _("Objects")},
            {
                "url": reverse("ooi_add_type_select", kwargs={"organization_code": self.organization.code}),
                "text": _("Add object"),
            },
        ]

        return context


class OOIAddView(BaseOOIFormView):
    template_name = "oois/ooi_add.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.ooi_class = self.get_ooi_class()
        self.initial = request.GET

    def get_ooi_class(self) -> type[OOI]:
        try:
            ooi_type = self.kwargs["ooi_type"]
            if ooi_type in EXCLUDE_OOI_TYPES:
                raise KeyError
            return type_by_name(ooi_type)
        except KeyError:
            raise Http404("OOI-type not found")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user_id"] = self.request.user.id

        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["type"] = self.ooi_class.get_ooi_type()
        context["breadcrumbs"] = [
            {"url": reverse("ooi_list", kwargs={"organization_code": self.organization.code}), "text": _("Objects")},
            {
                "url": reverse("ooi_add_type_select", kwargs={"organization_code": self.organization.code}),
                "text": _("Add object"),
            },
            {
                "url": reverse(
                    "ooi_add",
                    kwargs={"organization_code": self.organization.code, "ooi_type": self.ooi_class.get_ooi_type()},
                ),
                "text": _("Add %(ooi_type)s") % {"ooi_type": self.ooi_class.get_ooi_type()},
            },
        ]

        return context
