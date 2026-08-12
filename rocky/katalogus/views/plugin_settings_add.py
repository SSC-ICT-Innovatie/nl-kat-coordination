import structlog
from account.mixins import OrganizationPermissionRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from httpx import HTTPError

from katalogus.forms import PluginSchemaForm
from katalogus.views.mixins import SinglePluginView

logger = structlog.get_logger(__name__)


class PluginSettingsAddView(OrganizationPermissionRequiredMixin, SinglePluginView, FormView):
    """View to add a general setting for all plugins in KAT-alogus"""

    template_name = "plugin_settings_add.html"
    permission_required = "tools.can_set_katalogus_settings"

    def get_form(self, **kwargs):
        settings = self.katalogus_client.get_plugin_settings(self.plugin.id)

        # This helps mypy understand that self.plugin_schema can't be None
        # because of the check in dispatch()
        assert self.plugin_schema is not None

        return PluginSchemaForm(self.plugin_schema, settings, **self.get_form_kwargs())

    def dispatch(self, request, *args, **kwargs):
        if self.plugin_schema is None:
            messages.add_message(
                self.request,
                messages.WARNING,
                _("Trying to add settings to boefje without schema").format(self.plugin.id),
            )
            return redirect(self.get_success_url())

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if form.cleaned_data == {}:
            messages.add_message(
                self.request, messages.WARNING, _("No changes to the settings added: no form data present")
            )
            return redirect(self.get_success_url())

        try:
            self.katalogus_client.upsert_plugin_settings(self.plugin.id, form.cleaned_data)
            messages.add_message(self.request, messages.SUCCESS, _("Added settings for '{}'").format(self.plugin.name))
        except HTTPError:
            messages.add_message(self.request, messages.ERROR, _("Failed adding settings"))
            return redirect(self.get_success_url())

        if "add-enable" in self.request.POST:
            try:
                self.katalogus_client.enable_plugin(self.plugin)
            except HTTPError:
                messages.add_message(self.request, messages.ERROR, _("Enabling {} failed").format(self.plugin.name))
                return redirect(self.get_success_url())

            messages.add_message(self.request, messages.SUCCESS, _("Boefje '{}' enabled.").format(self.plugin.name))

        return redirect(self.get_success_url())

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
                    "plugin_settings_add",
                    kwargs={
                        "organization_code": self.organization.code,
                        "plugin_type": self.plugin.type,
                        "plugin_id": self.plugin.id,
                    },
                ),
                "text": _("Add settings"),
            },
        ]
        context["plugin_id"] = self.plugin.id
        context["plugin_type"] = self.plugin.type
        context["plugin_name"] = self.plugin.name
        return context

    def get_success_url(self):
        return reverse(
            "boefje_detail", kwargs={"organization_code": self.organization.code, "plugin_id": self.plugin.id}
        )

    def add_error_notification(self, message):
        messages.add_message(self.request, messages.ERROR, message)
