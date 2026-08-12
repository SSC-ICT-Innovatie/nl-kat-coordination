from account.mixins import OrganizationPermissionRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from katalogus.views.mixins import SinglePluginView
from rocky.views.scheduler import SchedulerView


class ChangeClearanceLevel(OrganizationPermissionRequiredMixin, SchedulerView, SinglePluginView, TemplateView):
    template_name = "change_clearance_level.html"
    permission_required = "tools.can_set_clearance_level"
    task_type = "boefje"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        if "selected_oois" in request.session:
            self.selected_oois = request.session["selected_oois"]
            self.oois = self.get_oois_objects_from_text_oois(self.selected_oois)

    def get(self, request, *args, **kwargs):
        if "selected_oois" not in request.session:
            messages.add_message(
                self.request, messages.ERROR, _("Session has terminated, please select objects again.")
            )
            return redirect(
                reverse(
                    "boefje_detail",
                    kwargs={"organization_code": self.organization.code, "plugin_id": kwargs["plugin_id"]},
                )
            )
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Start scanning oois at plugin detail page."""
        if not self.indemnification_present:
            return self.get(request, *args, **kwargs)

        self.run_boefje_for_oois(boefje=self.plugin, oois=self.oois)

        del request.session["selected_oois"]  # delete session
        return redirect(reverse("task_list", kwargs={"organization_code": self.organization.code}))

    def get_oois_objects_from_text_oois(self, oois):
        return [self.get_single_ooi(pk=ooi_id) for ooi_id in oois]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["plugin"] = self.plugin.model_dump()
        context["oois"] = self.oois
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
                    "change_clearance_level",
                    kwargs={
                        "organization_code": self.organization.code,
                        "plugin_type": self.plugin.type,
                        "plugin_id": self.plugin.id,
                        "scan_level": self.plugin.scan_level.value,
                    },
                ),
                "text": _("Change clearance level"),
            },
        ]
        return context
