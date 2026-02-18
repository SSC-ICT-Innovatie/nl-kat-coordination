import csv
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from crisis_room.forms import AddObjectListDashboardItemForm
from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from httpx import HTTPError
from tools.enums import CUSTOM_SCAN_LEVEL, SCAN_LEVEL
from tools.forms.ooi import SetClearanceLevelForm
from tools.forms.ooi_form import OOISearchForm, OOITypeMultiCheckboxForm
from tools.models import Indemnification
from tools.view_helpers import get_mandatory_fields

from octopoes.connector import RemoteException
from octopoes.models import EmptyScanProfile, Reference, ScanProfileType
from octopoes.models.exception import ObjectNotFoundException
from rocky.exceptions import (
    AcknowledgedClearanceLevelTooLowException,
    IndemnificationNotPresentException,
    TrustedClearanceLevelTooLowException,
)
from rocky.views.mixins import AddDashboardItemFormMixin, OctopoesView, OOIList
from rocky.views.ooi_view import BaseOOIListView


class PageActions(Enum):
    DELETE = "delete"
    UPDATE_SCAN_PROFILE = "update-scan-profile"
    ADD_TO_DASHBOARD = "add_to_dashboard"


class OOIListView(BaseOOIListView, OctopoesView, AddDashboardItemFormMixin):
    breadcrumbs = [{"url": reverse_lazy("ooi_list"), "text": gettext_lazy("Objects")}]
    template_name = "oois/ooi_list.html"
    add_dashboard_item_form = AddObjectListDashboardItemForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["ooi_type_form"] = OOITypeMultiCheckboxForm(self.request.GET)
        context["ooi_search_form"] = OOISearchForm(self.request.GET)
        context["edit_clearance_level_form"] = SetClearanceLevelForm
        context["mandatory_fields"] = get_mandatory_fields(self.request, params=["observed_at"])
        context["member"] = self.organization_member
        context["scan_levels"] = [alias for _, alias in CUSTOM_SCAN_LEVEL.choices]
        context["organization_indemnification"] = self.get_organization_indemnification
        context["breadcrumbs"] = [
            {"url": reverse("ooi_list", kwargs={"organization_code": self.organization.code}), "text": _("Objects")}
        ]

        return context

    def get(self, request: HttpRequest, *args: Any, status: int = 200, **kwargs: Any) -> HttpResponse:
        """Override the response status in case submitting a form returns an error message"""
        response = super().get(request, *args, **kwargs)
        response.status_code = status

        return response

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Perform bulk action on selected oois."""
        selected_oois = request.POST.getlist("ooi")
        action = request.POST.get("action")

        if not selected_oois and action != PageActions.ADD_TO_DASHBOARD.value:
            messages.add_message(request, messages.ERROR, _("No OOIs selected."))
            return self.get(request, status=422, *args, **kwargs)

        if action == PageActions.DELETE.value:
            return self._delete_oois(selected_oois, request, *args, **kwargs)

        if action == PageActions.UPDATE_SCAN_PROFILE.value:
            scan_type = request.POST.get("clearance_type")
            # Mypy doesn't understand that CUSTOM_SCAN_LEVEL is an enum without
            # the Django type hints
            if scan_type == ScanProfileType.INHERITED.value:
                return self._set_oois_to_inherit(selected_oois, request, *args, **kwargs)
            level = int(request.POST["level"])
            level = SCAN_LEVEL(level)
            return self._set_scan_profiles(selected_oois, level, request, *args, **kwargs)

        if action == PageActions.ADD_TO_DASHBOARD.value:
            return self.add_to_dashboard()

        messages.add_message(request, messages.ERROR, _("Unknown action."))
        return self.get(request, status=404, *args, **kwargs)

    def _set_scan_profiles(
        self, selected_oois: list[str], level: CUSTOM_SCAN_LEVEL, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        try:
            self.raise_clearance_levels([Reference.from_str(ooi) for ooi in selected_oois], level.value)
        except IndemnificationNotPresentException:
            messages.add_message(
                self.request,
                messages.ERROR,
                _("Could not raise clearance levels to L%s. Indemnification not present at organization %s.")
                % (level.value, self.organization.name),
            )
            return self.get(request, status=403, *args, **kwargs)
        except TrustedClearanceLevelTooLowException:
            messages.add_message(
                self.request,
                messages.ERROR,
                _(
                    "Could not raise clearance level to L%s. "
                    "You were trusted a clearance level of L%s. "
                    "Contact your administrator to receive a higher clearance."
                )
                % (level.value, self.organization_member.max_clearance_level),
            )
            return self.get(request, status=403, *args, **kwargs)
        except AcknowledgedClearanceLevelTooLowException:
            messages.add_message(
                self.request,
                messages.ERROR,
                _(
                    "Could not raise clearance level to L%s. "
                    "You acknowledged a clearance level of L%s. "
                    "Please accept the clearance level below to proceed."
                )
                % (level.value, self.organization_member.acknowledged_clearance_level),
            )
            return redirect(reverse("account_detail", kwargs={"organization_code": self.organization.code}))

        except (HTTPError, RemoteException, ConnectionError):
            messages.add_message(request, messages.ERROR, _("An error occurred while saving clearance levels."))

            return self.get(request, status=500, *args, **kwargs)
        except ObjectNotFoundException:
            messages.add_message(
                request,
                messages.ERROR,
                _("An error occurred while saving clearance levels.") + _("One of the OOI's doesn't exist"),
            )
            return self.get(request, status=404, *args, **kwargs)

        messages.add_message(
            request,
            messages.SUCCESS,
            _("Successfully set scan profile to %s for %d OOIs.") % (level.name, len(selected_oois)),
        )
        return redirect(reverse("ooi_list", kwargs={"organization_code": self.organization.code}))

    def _set_oois_to_inherit(
        self, selected_oois: list[str], request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        scan_profiles = [EmptyScanProfile(reference=Reference.from_str(ooi)) for ooi in selected_oois]

        try:
            self.octopoes_api_connector.save_many_scan_profiles(scan_profiles, valid_time=datetime.now(timezone.utc))
        except (HTTPError, RemoteException, ConnectionError):
            messages.add_message(
                request, messages.ERROR, _("An error occurred while setting clearance levels to inherit.")
            )
            return self.get(request, status=500, *args, **kwargs)
        except ObjectNotFoundException:
            messages.add_message(
                request,
                messages.ERROR,
                _("An error occurred while setting clearance levels to inherit: one of the OOIs doesn't exist."),
            )
            return self.get(request, status=404, *args, **kwargs)

        messages.add_message(
            request, messages.SUCCESS, _("Successfully set %d OOI(s) clearance level to inherit.") % len(selected_oois)
        )
        return redirect(reverse("ooi_list", kwargs={"organization_code": self.organization.code}))

    def _delete_oois(self, selected_oois: list[str], request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        connector = self.octopoes_api_connector
        valid_time = datetime.now(timezone.utc)

        try:
            connector.delete_many([Reference.from_str(ooi) for ooi in selected_oois], valid_time)
        except (HTTPError, RemoteException, ConnectionError):
            messages.add_message(request, messages.ERROR, _("An error occurred while deleting oois."))
            return self.get(request, status=500, *args, **kwargs)
        except ObjectNotFoundException:
            messages.add_message(
                request, messages.ERROR, _("An error occurred while deleting OOIs: one of the OOIs doesn't exist.")
            )
            return self.get(request, status=404, *args, **kwargs)

        messages.add_message(
            request,
            messages.SUCCESS,
            _("Successfully deleted %d ooi(s). Note: Bits can recreate objects automatically.") % len(selected_oois),
        )

        return redirect(reverse("ooi_list", kwargs={"organization_code": self.organization.code}))

    def get_organization_indemnification(self):
        return Indemnification.objects.filter(organization=self.organization).exists()


class OOIListExportView(BaseOOIListView):
    def get(self, request, *args, **kwargs):
        file_type = request.GET.get("file_type")
        filters = self.get_active_filters()

        queryset = self.get_queryset()
        ooi_list = queryset[: OOIList.HARD_LIMIT]

        exports = [{"observed_at": str(self.observed_at), "filters": str(filters)}]

        for ooi in ooi_list:
            exports.append({"key": ooi.primary_key, "name": ooi.human_readable, "ooi_type": ooi.ooi_type})

        if file_type == "json":
            response = HttpResponse(
                json.dumps(exports),
                content_type="application/json",
                headers={"Content-Disposition": "attachment; filename=ooi_list_" + str(self.observed_at) + ".json"},
            )

            return response

        elif file_type == "csv":
            response = HttpResponse(
                content_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=ooi_list_" + str(self.observed_at) + ".csv"},
            )

            writer = csv.writer(response)
            writer.writerow(["observed_at", "filters"])
            writer.writerow([str(self.observed_at), str(filters)])
            writer.writerow(["key", "name", "ooi_type"])
            for ooi in ooi_list:
                writer.writerow([ooi.primary_key, ooi.human_readable, ooi.ooi_type])

            return response

        else:
            raise Http404("Export type not found")
