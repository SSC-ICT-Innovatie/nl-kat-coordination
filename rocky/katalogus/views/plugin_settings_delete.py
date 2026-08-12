import structlog
from account.mixins import OrganizationPermissionRequiredMixin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from httpx import HTTPError, HTTPStatusError, codes

from katalogus.views.mixins import SinglePluginView

logger = structlog.get_logger(__name__)


class PluginSettingsDeleteView(OrganizationPermissionRequiredMixin, SinglePluginView, TemplateView):
    template_name = "plugin_settings_delete.html"
    permission_required = "tools.can_set_katalogus_settings"

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["breadcrumbs"] = [
            {
                "url": reverse("katalogus", kwargs={"organization_code": self.organization.code}),
                "text": _("KAT-alogus"),
            },
            {
                "url": reverse(
                    "boefje_detail", kwargs={"organization_code": self.organization.code, "plugin_id": self.plugin.id}
                ),
                "text": self.plugin.name,
            },
            {
                "url": reverse(
                    "plugin_settings_delete",
                    kwargs={
                        "organization_code": self.organization.code,
                        "plugin_type": self.plugin.type,
                        "plugin_id": self.plugin.id,
                    },
                ),
                "text": _("Delete"),
            },
        ]
        context["plugin_id"] = self.plugin.id
        context["plugin_type"] = self.plugin.type
        context["plugin_name"] = self.plugin.name
        context["cancel_url"] = self.get_success_url()
        return context

    def get_success_url(self):
        return reverse(
            "boefje_detail", kwargs={"organization_code": self.organization.code, "plugin_id": self.plugin.id}
        )

    def delete(self, request, *args, **kwargs):
        try:
            self.katalogus_client.delete_plugin_settings(self.plugin.id)
            messages.add_message(
                request, messages.SUCCESS, _("Settings for plugin {} successfully deleted.").format(self.plugin.name)
            )
        except HTTPError as e:
            if isinstance(e, HTTPStatusError) and e.response.status_code == codes.NOT_FOUND:
                messages.add_message(
                    request, messages.WARNING, _("Plugin {} has no settings.").format(self.plugin.name)
                )
            else:
                messages.add_message(
                    request,
                    messages.ERROR,
                    _("Failed deleting Settings for plugin {}. Check the Katalogus logs for more info.").format(
                        self.plugin.name
                    ),
                )
        finally:
            return HttpResponseRedirect(self.get_success_url())
