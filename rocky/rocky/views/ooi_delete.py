from account.mixins import OrganizationPermissionRequiredMixin
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from rocky.views.mixins import SingleOOIMixin


class OOIDeleteView(OrganizationPermissionRequiredMixin, SingleOOIMixin, TemplateView):
    template_name = "oois/ooi_delete.html"
    permission_required = "tools.can_delete_oois"

    def delete(self, request):
        # Deleting at the viewed valid-time is intentional: a historic view deletes at that
        # moment, "now" is the default when no temporal context is set (underdarknl, #5227).
        self.octopoes_api_connector.delete(self.ooi.reference, self.observed_at, sync=True)
        return HttpResponseRedirect(self.get_success_url())

    # Add support for browsers which only accept GET and POST for now.
    def post(self, request, **kwargs):
        return self.delete(request)

    def get_success_url(self):
        return reverse_lazy(
            "ooi_list", kwargs={"organization_code": self.organization.code, "temporal_context": self.temporal_context}
        )

    def build_breadcrumbs(self):
        return [
            *super().build_breadcrumbs(),
            {
                "url": reverse_lazy(
                    "ooi_delete",
                    kwargs={
                        "organization_code": self.organization.code,
                        "temporal_context": self.temporal_context,
                        "ooi": self.ooi,
                    },
                ),
                "text": _("Delete"),
            },
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["props"] = self.ooi.model_dump()
        context["breadcrumbs"] = self.build_breadcrumbs()

        return context
