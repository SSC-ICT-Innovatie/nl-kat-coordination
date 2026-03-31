from account.forms.organization import OrganizationListForm
from account.mixins import OrganizationPermissionRequiredMixin, OrganizationView
from account.models import KATUser
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.urls.base import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView
from httpx import HTTPError
from structlog import get_logger
from tools.models import Organization

logger = get_logger(__name__)


class ConfirmCloneSettingsView(
    OrganizationPermissionRequiredMixin, OrganizationView, UserPassesTestMixin, TemplateView
):
    template_name = "confirmation_clone_settings.html"
    permission_required = "tools.can_set_katalogus_settings"

    def test_func(self):
        user: KATUser = self.request.user
        return self.kwargs["to_organization"] in {org.code for org in user.organizations}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["to_organization"] = Organization.objects.get(code=kwargs["to_organization"])

        return context

    def post(self, request, *args, **kwargs):
        to_organization = Organization.objects.get(code=kwargs["to_organization"])
        logger.info("Cloning organization settings", event_code=910000, to_organization_code=to_organization.code)
        self.katalogus_client.clone_all_configuration_to_organization(to_organization.code)
        messages.add_message(
            self.request,
            messages.SUCCESS,
            _("Settings from {} to {} successfully cloned.").format(self.organization.name, to_organization.name),
        )
        return HttpResponseRedirect(reverse("katalogus_settings", kwargs={"organization_code": self.organization.code}))


class KATalogusSettingsView(OrganizationPermissionRequiredMixin, OrganizationView, FormView):
    """View that gives an overview of all plugins settings"""

    template_name = "katalogus_settings.html"
    permission_required = "tools.can_view_katalogus_settings"
    plugin_type = "boefjes"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {
                "url": reverse("katalogus", kwargs={"organization_code": self.organization.code}),
                "text": _("KAT-alogus"),
            },
            {
                "url": reverse("katalogus_settings", kwargs={"organization_code": self.organization.code}),
                "text": _("Settings"),
            },
        ]
        context["plugin_type"] = self.plugin_type
        context["settings"] = self.get_settings()

        return context

    def get_settings(self):
        all_plugins_settings = []

        for boefje in self.katalogus_client.get_boefjes():
            try:
                plugin_setting = self.katalogus_client.get_plugin_settings(boefje.id)
            except HTTPError:
                messages.add_message(
                    self.request, messages.ERROR, _("Failed getting settings for boefje {}").format(self.plugin.id)
                )
                continue

            if not plugin_setting:
                continue

            for key, value in plugin_setting.items():
                all_plugins_settings.append(
                    {"plugin_id": boefje.id, "plugin_name": boefje.name, "name": key, "value": value}
                )

        return all_plugins_settings

    def get_form(self, form_class=None):
        return OrganizationListForm(
            user=self.request.user, exclude_organization=self.organization, **self.get_form_kwargs()
        )

    def form_valid(self, form):
        return HttpResponseRedirect(self.get_success_url(to_organization=form.cleaned_data["organization"]))

    def get_success_url(self, **kwargs):
        return reverse_lazy(
            "confirm_clone_settings",
            kwargs={"organization_code": self.organization.code, "to_organization": kwargs["to_organization"]},
        )
