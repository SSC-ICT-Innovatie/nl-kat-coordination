from typing import Any

import structlog
from account.mixins import OrganizationView
from django.contrib import messages
from django.http import Http404, HttpRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from httpx import HTTPError, HTTPStatusError
from rest_framework.status import HTTP_404_NOT_FOUND

from katalogus.client import Boefje, KATalogus, Plugin

logger = structlog.get_logger(__name__)


class SinglePluginView(OrganizationView):
    katalogus_client: KATalogus
    plugin: Plugin

    def setup(self, request: HttpRequest, *args: Any, plugin_id: str, **kwargs: Any) -> None:
        """
        Prepare organization info and KAT-alogus API client.
        """
        super().setup(request, *args, plugin_id=plugin_id, **kwargs)

        try:
            self.plugin = self.katalogus_client.get_plugin(plugin_id)
            self.plugin_schema = self.plugin.boefje_schema if isinstance(self.plugin, Boefje) else None
        except HTTPError as exc:
            if isinstance(exc, HTTPStatusError) and exc.response.status_code == HTTP_404_NOT_FOUND:
                raise Http404(f"Plugin {plugin_id} not found.")
            messages.add_message(
                self.request,
                messages.ERROR,
                _("Getting information for plugin {} failed. Please check the KATalogus logs.").format(plugin_id),
            )
            raise

    def dispatch(self, request, *args, **kwargs):
        if not self.plugin:
            return redirect(reverse("katalogus", kwargs={"organization_code": self.organization.code}))

        return super().dispatch(request, *args, **kwargs)

    def is_required_field(self, field: str) -> bool:
        """Check whether this field should be required, defaults to False."""
        return bool(self.plugin_schema and field in self.plugin_schema.get("required", []))

    def is_secret_field(self, field: str) -> bool:
        """Check whether this field should be secret, defaults to False."""
        return bool(self.plugin_schema and field in self.plugin_schema.get("secret", []))
