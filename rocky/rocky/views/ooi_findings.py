from urllib.parse import quote

from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from tools.forms.base import ObservedAtForm
from tools.view_helpers import Breadcrumb

from rocky.views.ooi_detail_related_object import OOIFindingManager
from rocky.views.ooi_view import BaseOOIDetailView


class OOIFindingListView(OOIFindingManager, BaseOOIDetailView, TemplateView):
    template_name = "oois/ooi_findings.html"
    connector_form_class = ObservedAtForm

    def build_breadcrumbs(self) -> list[Breadcrumb]:
        breadcrumbs = super().build_breadcrumbs()
        breadcrumbs.append(self.get_last_breadcrumb())
        return breadcrumbs

    def get_last_breadcrumb(self) -> Breadcrumb:
        return {
            "url": reverse(
                "ooi_findings",
                kwargs={
                    "organization_code": self.organization.code,
                    "temporal_context": self.temporal_context,
                    "ooi": quote(self.ooi.primary_key, safe=""),
                },
            ),
            "text": _("Object findings"),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["findings"] = self.get_finding_details_sorted_by_score_desc()
        context["breadcrumbs"] = self.build_breadcrumbs()
        return context
