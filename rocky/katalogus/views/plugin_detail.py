from datetime import datetime, timezone
from typing import Any

from account.mixins import OrganizationView
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import redirect
from django.urls.base import reverse
from django.utils.translation import gettext_lazy as _
from tools.forms.ooi import SelectOOIFilterForm, SelectOOIForm

from katalogus.client import Boefje, Normalizer
from katalogus.views.plugin_settings_list import PluginSettingsListView
from octopoes.models import ScanLevel
from octopoes.models.types import OOIType
from rocky.scheduler import ScheduleResponse
from rocky.views.tasks import TaskListView


class PluginCoverImgView(OrganizationView):
    """Get the cover image of a plugin."""

    def get(self, request, *args, **kwargs):
        file = FileResponse(self.get_katalogus().get_cover(kwargs["plugin_id"]))
        file.headers["Cache-Control"] = "max-age=604800"
        return file


class PluginDetailView(TaskListView, PluginSettingsListView):
    def post(self, request, *args, **kwargs):
        if self.action == self.SCAN_OOIS:
            selected_oois = request.POST.getlist("ooi", [])

            if selected_oois and self.plugin.id:
                oois = self.get_oois(selected_oois)
                boefje = self.katalogus_client.get_plugin(self.plugin.id)

                oois_with_clearance_level = oois["oois_with_clearance"]
                oois_without_clearance_level = oois["oois_without_clearance"]

                if oois_with_clearance_level:
                    self.run_boefje_for_oois(boefje=boefje, oois=oois_with_clearance_level)

                if oois_without_clearance_level:
                    if not self.organization_member.has_perm("tools.can_set_clearance_level"):
                        messages.error(
                            request,
                            _(
                                "Some selected OOIs needs an increase of clearance level to perform scans."
                                " You do not have the permission to change clearance level."
                            ),
                        )
                    else:
                        request.session["selected_oois"] = oois_without_clearance_level
                        return redirect(
                            reverse(
                                "change_clearance_level",
                                kwargs={
                                    "plugin_type": "boefje",
                                    "organization_code": self.organization.code,
                                    "plugin_id": self.plugin.id,
                                    "scan_level": self.plugin.scan_level.value,
                                },
                            )
                        )
        return super().post(request, *args, **kwargs)

    def get_task_filters(self) -> dict[str, str | datetime | None]:
        filters = super().get_task_filters()
        filters["filters"]["filters"].append(
            {"column": "data", "field": f"{self.task_type}__id", "operator": "==", "value": self.plugin.id}
        )
        return filters

    def get_oois(self, selected_oois: list[str]) -> dict[str, Any]:
        oois_with_clearance = []
        oois_without_clearance = []
        for ooi in selected_oois:
            ooi_object = self.get_single_ooi(pk=ooi)

            if ooi_object.scan_profile and ooi_object.scan_profile.level >= self.plugin.scan_level.value:
                oois_with_clearance.append(ooi_object)
            else:
                oois_without_clearance.append(ooi_object.primary_key)

        return {"oois_with_clearance": oois_with_clearance, "oois_without_clearance": oois_without_clearance}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["plugin"] = self.plugin.model_dump()
        self.check_plugin_type()
        context["plugin_settings"] = self.get_plugin_settings()
        return context

    def check_plugin_type(self):
        if self.plugin.type != self.task_type:
            # It would be nicer if we could redirect, but Django doesn't have an easy way to do that.
            raise Http404("Plugin type does not match url.")


class NormalizerDetailView(PluginDetailView):
    template_name = "normalizer_detail.html"
    plugin: Normalizer
    task_type = "normalizer"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {
                "url": reverse("katalogus", kwargs={"organization_code": self.organization.code}),
                "text": _("KAT-alogus"),
            },
            {
                "url": reverse(
                    "normalizer_detail",
                    kwargs={"organization_code": self.organization.code, "plugin_id": self.plugin.id},
                ),
                "text": self.plugin.name,
            },
        ]

        return context


class BoefjeDetailView(PluginDetailView):
    """Detail view for a specific boefje. Shows boefje settings and consumable oois for scanning."""

    template_name = "boefje_detail.html"
    limit_ooi_list = 150
    plugin: Boefje
    task_type = "boefje"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["new_variant"] = self.request.GET.get("new_variant")
        context["variants"] = self.get_katalogus().get_plugins(oci_image=self.plugin.oci_image)

        for variant in context["variants"]:
            if variant.created:
                variant.created = datetime.fromisoformat(variant.created)

        context["select_ooi_filter_form"] = SelectOOIFilterForm
        if "show_all" in self.request.GET:
            context["select_oois_form"] = SelectOOIForm(
                oois=self.get_form_consumable_oois(), organization_code=self.organization.code
            )
        else:
            context["select_oois_form"] = SelectOOIForm(
                oois=self.get_form_filtered_consumable_oois(), organization_code=self.organization.code
            )

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
        ]

        return context

    def get_form_consumable_oois(self) -> list[tuple[OOIType, ScheduleResponse | None]]:
        """Get all available OOIS that plugin can consume."""

        oois = {
            ooi.primary_key: ooi
            for ooi in self.octopoes_api_connector.list_objects(
                self.plugin.consumes, valid_time=datetime.now(timezone.utc), limit=self.limit_ooi_list
            ).items
        }

        return self._filter_oois_with_schedules(oois)

    def get_form_filtered_consumable_oois(self) -> list[tuple[OOIType, ScheduleResponse | None]]:
        """Return a list of oois that is filtered for oois that meets clearance level."""
        oois = {
            ooi.primary_key: ooi
            for ooi in self.octopoes_api_connector.list_objects(
                self.plugin.consumes,
                valid_time=datetime.now(timezone.utc),
                limit=self.limit_ooi_list,
                scan_level={level for level in ScanLevel if level.value >= self.plugin.scan_level.value},
            ).items
        }

        return self._filter_oois_with_schedules(oois)

    def _filter_oois_with_schedules(self, oois: dict[str, OOIType]) -> list[tuple[OOIType, ScheduleResponse | None]]:
        if not oois:
            return []

        schedules = self.scheduler_client.post_schedule_search(
            {
                "filters": [
                    {"column": "data", "field": "boefje__id", "operator": "eq", "value": self.plugin.id},
                    {
                        "column": "data",
                        "field": "input_ooi",
                        "operator": "in",
                        "value": [o.primary_key for o in oois.values()],
                    },
                ]
            }
        )

        results: dict[str, tuple[OOIType, ScheduleResponse | None]] = {}
        # corner case, not all valid Input OOI's might have a schedule
        # this happens when a boefje is edited (eg, new input types).
        for ooi in oois.values():
            results[ooi.primary_key] = (ooi, None)

        for schedule in schedules.results:
            if "input_ooi" in schedule.data:
                key = schedule.data["input_ooi"]
                results[key] = (oois[key], schedule)

        return list(results.values())
