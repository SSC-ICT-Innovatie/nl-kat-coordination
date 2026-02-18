from datetime import datetime, timezone
from typing import Any

import structlog
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from tools.forms.ooi import SetClearanceLevelForm
from tools.view_helpers import get_mandatory_fields, get_ooi_url

from octopoes.models import DeclaredScanProfile, EmptyScanProfile, ScanProfileType
from rocky.views.ooi_detail import OOIDetailView

logger = structlog.get_logger(__name__)


class ScanProfileDetailView(FormView, OOIDetailView):
    template_name = "scan_profiles/scan_profile_detail.html"
    form_class = SetClearanceLevelForm

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["mandatory_fields"] = get_mandatory_fields(self.request)
        if self.ooi.scan_profile and self.ooi.scan_profile.user_id:
            try:
                context["scan_profile_user"] = get_user_model().objects.get(id=self.ooi.scan_profile.user_id)
            except get_user_model().DoesNotExist:
                pass
        return context

    def get_initial(self):
        initial = super().get_initial()

        if not self.ooi.scan_profile or isinstance(self.ooi.scan_profile, EmptyScanProfile):
            return initial

        initial["clearance_type"] = self.ooi.scan_profile.scan_profile_type

        if isinstance(self.ooi.scan_profile, DeclaredScanProfile):
            initial["level"] = self.ooi.scan_profile.level

        return initial

    def post(self, request, *args, **kwargs):
        try:
            clearance_type = self.request.POST["clearance_type"]
            super().post(request, *args, **kwargs)
            if clearance_type == ScanProfileType.INHERITED.value:
                self.octopoes_api_connector.save_scan_profile(
                    EmptyScanProfile(reference=self.ooi.reference), valid_time=datetime.now(timezone.utc)
                )
                logger.info("Scan profiles set to empty", event_code="800011", ooi=self.ooi.reference)
        except (ValueError, KeyError):
            messages.error(
                self.request, _("Cannot set clearance level. The clearance type must be inherited or declared.")
            )
        return redirect(get_ooi_url("scan_profile_detail", self.ooi.primary_key, self.organization.code))
