from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView, View

from rocky.views.mixins import OctopoesView


class NibblesToggleView(OctopoesView, View):
    def post(self, request, *args, **kwargs):
        nibble_id = str(kwargs.get("nibble_id", ""))
        new_state = kwargs.get("state") == "enable"
        self.octopoes_api_connector.toggle_nibbles([nibble_id], new_state)
        return HttpResponseRedirect(
            reverse(
                "nibbles_list",
                kwargs={"organization_code": self.organization.code, "view_type": request.GET.get("view_type", "grid")},
            )
        )


class NibblesView(OctopoesView, ListView):
    """Showing only Nibbles in KAT-alogus"""

    template_name = "nibbles.html"

    def get_queryset(self):
        return self.octopoes_api_connector.list_nibbles()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["view_type"] = self.kwargs.get("view_type", "grid")
        context["url_name"] = self.request.resolver_match.url_name
        context["breadcrumbs"] = [
            {"url": reverse("katalogus", kwargs={"organization_code": self.organization.code}), "text": _("KAT-alogus")}
        ]
        context["enabled_nibbles"] = self.octopoes_api_connector.list_enabled_nibbles()
        return context
