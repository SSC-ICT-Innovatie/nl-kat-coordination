from typing import Any

from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from httpx import HTTPError

from katalogus.views.mixins import SinglePluginView
from rocky.paginator import RockyPaginator


class PluginSettingsListView(SinglePluginView):
    """
    Shows all settings available for a specific plugin (plugin schema settings).
    """

    paginator_class = RockyPaginator
    paginate_by = 150
    context_object_name = "plugin_settings"

    def get_plugin_settings(self) -> list[dict[str, Any]]:
        """Gets schema setting with additional info of the value of a setting."""
        if not self.organization_member.has_perm("tools.can_view_katalogus_settings"):
            return []
        if self.plugin_schema is None:
            return []

        try:
            settings = self.katalogus_client.get_plugin_settings(plugin_id=self.plugin.id)

        except HTTPError:
            messages.add_message(
                self.request, messages.ERROR, _("Failed getting settings for boefje {}").format(self.plugin.id)
            )
            return []

        props = self.plugin_schema.get("properties", [])

        return [
            {
                "name": prop,
                "value": settings.get(prop),
                "required": self.is_required_field(prop),
                "secret": self.is_secret_field(prop),
            }
            for prop in props
        ]
