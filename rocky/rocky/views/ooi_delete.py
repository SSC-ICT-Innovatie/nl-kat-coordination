from datetime import datetime, timezone

from account.mixins import OrganizationPermissionRequiredMixin
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from tools.view_helpers import get_ooi_url

from rocky.views.mixins import SingleOOIMixin


class OOIDeleteView(OrganizationPermissionRequiredMixin, SingleOOIMixin, TemplateView):
    template_name = "oois/ooi_delete.html"
    permission_required = "tools.can_delete_oois"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.ooi = self.get_ooi()

    def delete(self, request):
        self.octopoes_api_connector.delete(self.ooi.reference, valid_time=datetime.now(timezone.utc), sync=True)
        return HttpResponseRedirect(self.get_success_url())

    # Add support for browsers which only accept GET and POST for now.
    def post(self, request, **kwargs):
        return self.delete(request)

    def get_success_url(self):
        return reverse_lazy("ooi_list", kwargs={"organization_code": self.organization.code})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Construct breadcrumbs
        breadcrumb_list = self.get_breadcrumb_list()
        breadcrumb_list.append(
            {
                "url": get_ooi_url("ooi_delete", self.ooi.primary_key, organization_code=self.organization.code),
                "text": _("Delete"),
            }
        )

        context["ooi"] = self.ooi
        context["props"] = self.ooi.model_dump()
        context["breadcrumbs"] = breadcrumb_list

        return context
