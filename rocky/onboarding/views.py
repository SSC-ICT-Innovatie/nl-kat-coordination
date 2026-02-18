from datetime import datetime, timedelta, timezone
from typing import Any

from account.forms import OnboardingOrganizationUpdateForm, OrganizationForm
from account.mixins import OrganizationPermissionRequiredMixin, OrganizationView
from account.views import OOIClearanceMixin
from crisis_room.management.commands.dashboards import run_findings_dashboard
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.urls.base import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from django.views.generic.edit import CreateView, FormView, UpdateView
from httpx import HTTPError
from katalogus.client import Plugin
from reports.report_types.definitions import ReportPlugins
from reports.report_types.dns_report.report import DNSReport
from reports.views.base import BaseReportView, get_selection
from structlog import get_logger
from tools.models import Organization, OrganizationMember
from tools.ooi_helpers import get_or_create_ooi
from tools.view_helpers import Breadcrumb

from octopoes.models import OOI
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network
from octopoes.models.ooi.web import URL
from onboarding.forms import OnboardingCreateObjectURLForm, OnboardingSetClearanceLevelForm
from onboarding.view_helpers import (
    DNS_REPORT_LEAST_CLEARANCE_LEVEL,
    ONBOARDING_PERMISSIONS,
    IntroductionRegistrationStepsMixin,
    IntroductionStepsMixin,
)
from rocky.exceptions import RockyError
from rocky.views.indemnification_add import IndemnificationAddView
from rocky.views.ooi_view import SingleOOIMixin, SingleOOITreeMixin
from rocky.views.scheduler import SchedulerView

User = get_user_model()


logger = get_logger(__name__)


class OnboardingStart(OrganizationView):
    def get(self, request, *args, **kwargs):
        if request.user.is_superuser:
            return redirect("step_1_introduction_registration")
        if self.organization_member.has_perms(ONBOARDING_PERMISSIONS):
            return redirect("step_1a_introduction", kwargs={"organization_code": self.organization.code})
        return redirect("crisis_room")


class OnboardingIntroductionView(
    OrganizationPermissionRequiredMixin, IntroductionStepsMixin, OrganizationView, TemplateView
):
    """
    1. Start the onboarding wizard. What is OpenKAT and what it does.
    """

    template_name = "step_1a_introduction.html"
    current_step = 1
    permission_required = "tools.can_scan_organization"


class OnboardingIntroductionRegistrationView(PermissionRequiredMixin, IntroductionRegistrationStepsMixin, TemplateView):
    """
    Step: 1 - Registration introduction
    """

    template_name = "step_1_introduction_registration.html"
    current_step = 1
    permission_required = "tools.add_organizationmember"


class OnboardingOrganizationSetupView(PermissionRequiredMixin, IntroductionRegistrationStepsMixin, CreateView):
    """
    Step 2a: Create a new organization
    """

    model = Organization
    template_name = "step_2a_organization_setup.html"
    form_class = OrganizationForm
    current_step = 2
    permission_required = "tools.add_organization"

    def get(self, request, *args, **kwargs):
        if member := OrganizationMember.objects.filter(user=self.request.user).first():
            return redirect(
                reverse("step_2b_organization_update", kwargs={"organization_code": member.organization.code})
            )
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except RockyError as e:
            messages.add_message(request, messages.ERROR, str(e))

        return self.get(request, *args, **kwargs)

    def get_success_url(self) -> str:
        self.create_first_member(self.object)
        return reverse_lazy("step_3_indemnification_setup", kwargs={"organization_code": self.object.code})

    def form_valid(self, form):
        org_name = form.cleaned_data["name"]
        result = super().form_valid(form)
        self.add_success_notification(org_name)
        return result

    def create_first_member(self, organization):
        member = OrganizationMember.objects.create(user=self.request.user, organization=organization)
        if member.user.is_superuser:
            member.trusted_clearance_level = 4
            member.acknowledged_clearance_level = 4
            member.save()

    def add_success_notification(self, org_name):
        success_message = _("{org_name} successfully created.").format(org_name=org_name)
        messages.add_message(self.request, messages.SUCCESS, success_message)


class OnboardingOrganizationUpdateView(
    OrganizationPermissionRequiredMixin, IntroductionStepsMixin, OrganizationView, UpdateView
):
    """
    Step 2b: Update an existing organization (only name not code)
    """

    model = Organization
    template_name = "step_2b_organization_update.html"
    form_class = OnboardingOrganizationUpdateForm
    current_step = 2
    permission_required = "tools.change_organization"

    def get_object(self, queryset=None):
        return self.organization

    def get_success_url(self) -> str:
        return reverse_lazy("step_3_indemnification_setup", kwargs={"organization_code": self.organization.code})

    def form_valid(self, form):
        org_name = form.cleaned_data["name"]
        self.add_success_notification(org_name)
        return super().form_valid(form)

    def add_success_notification(self, org_name):
        success_message = _("{org_name} successfully updated.").format(org_name=org_name)
        messages.add_message(self.request, messages.SUCCESS, success_message)


class OnboardingIndemnificationSetupView(IntroductionStepsMixin, IndemnificationAddView):
    """
    Step 3: Agree to idemnification to scan oois
    """

    current_step = 2
    template_name = "step_3_indemnification_setup.html"

    def get_success_url(self) -> str:
        return reverse_lazy(
            "step_4_trusted_acknowledge_clearance_level", kwargs={"organization_code": self.organization.code}
        )


class OnboardingAcknowledgeClearanceLevelView(
    IntroductionStepsMixin, OOIClearanceMixin, OrganizationView, TemplateView
):
    """
    4. Explains the user that before setting a clearance level, they must have a permission to do so.
    Here they acknowledge the clearance level assigned by their administrator.
    """

    template_name = "step_4_trusted_acknowledge_clearance_level.html"
    permission_required = "tools.can_set_clearance_level"
    current_step = 2

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ooi"] = self.request.GET.get("ooi", "")
        context["dns_report_least_clearance_level"] = DNS_REPORT_LEAST_CLEARANCE_LEVEL
        return context


class OnboardingSetupScanOOIAddView(
    OrganizationPermissionRequiredMixin, IntroductionStepsMixin, SingleOOITreeMixin, FormView
):
    """
    5. The user will create a URL object. Shows a form and validation to create object.
    """

    template_name = "step_5_add_scan_ooi.html"
    current_step = 3
    permission_required = "tools.can_scan_organization"
    form_class = OnboardingCreateObjectURLForm

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)

    def get_or_create_url_object(self, url: str) -> OOI:
        network = Network(name="internet")
        url = URL(network=network.reference, raw=url, user_id=self.request.user.id)
        observed_at = datetime.now(timezone.utc)
        url_ooi, _ = get_or_create_ooi(self.octopoes_api_connector, self.bytes_client, url, observed_at)
        return url_ooi

    def form_valid(self, form):
        cleaned_url = form.cleaned_data["url"]
        ooi = self.get_or_create_url_object(cleaned_url)
        selection = {"ooi": ooi.primary_key}
        return redirect(
            reverse("step_6_set_clearance_level", kwargs={"organization_code": self.organization.code})
            + get_selection(self.request, selection)
        )

    def build_breadcrumbs(self) -> list[Breadcrumb]:
        return super().build_breadcrumbs() + [
            {
                "url": reverse("step_6_set_clearance_level", kwargs={"organization_code": self.organization.code})
                + get_selection(self.request),
                "text": _("Creating an object"),
            }
        ]


class OnboardingSetClearanceLevelView(
    OrganizationPermissionRequiredMixin, IntroductionStepsMixin, SingleOOITreeMixin, FormView
):
    """
    6. Set the actual clearance level on the object created before.
    """

    template_name = "step_6_set_clearance_level.html"
    permission_required = "tools.can_set_clearance_level"
    current_step = 3
    form_class = OnboardingSetClearanceLevelForm
    initial = {"level": DNS_REPORT_LEAST_CLEARANCE_LEVEL}

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.url = self.request.GET.get("ooi", "")
        self.selection = {"ooi": self.url}

    def form_valid(self, form):
        ooi = self.get_ooi(self.url)
        if not self.can_raise_clearance_level(ooi, DNS_REPORT_LEAST_CLEARANCE_LEVEL):
            return self.get(self.request, self.args, self.kwargs)
        return redirect(
            reverse("step_7_clearance_level_introduction", kwargs={"organization_code": self.organization.code})
            + get_selection(self.request, self.selection)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ooi"] = self.url
        context["dns_report_least_clearance_level"] = DNS_REPORT_LEAST_CLEARANCE_LEVEL
        return context


class OnboardingClearanceLevelIntroductionView(
    OrganizationPermissionRequiredMixin, IntroductionStepsMixin, OrganizationView, TemplateView
):
    """
    7. Explanation what clearance levels mean.
    """

    template_name = "step_7_clearance_level_introduction.html"
    permission_required = "tools.can_set_clearance_level"
    current_step = 4

    def get_boefjes_tiles(self) -> list[dict[str, Any]]:
        tiles = [
            {
                "id": "dns_zone",
                "type": "boefje",
                "scan_level": "1",
                "name": "DNS-Zone",
                "description": _("Fetch the parent DNS zone of a hostname"),
                "enabled": False,
            },
            {
                "id": "fierce",
                "type": "boefje",
                "scan_level": "3",
                "name": "Fierce",
                "description": _("Finds subdomains by brute force"),
                "enabled": False,
            },
        ]
        return tiles

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ooi"] = self.request.GET.get("ooi", "")
        context["boefjes"] = self.get_boefjes_tiles()
        return context


class OnboardingSetupScanSelectPluginsView(
    OrganizationPermissionRequiredMixin, IntroductionStepsMixin, OrganizationView, TemplateView
):
    """
    8. Shows the user all required and optional plugins to select from. Required plugins are mandatory to continue.
    """

    template_name = "step_8_setup_scan_select_plugins.html"
    permission_required = "tools.can_enable_disable_boefje"
    current_step = 4
    plugins: ReportPlugins = DNSReport.plugins

    def get_plugins(self) -> dict[str, list[Plugin]]:
        all_plugins = {}
        katalogus = self.get_katalogus()
        for required_optional, plugin_ids in self.plugins.items():
            plugins = katalogus.get_plugins(ids=[plugin_id for plugin_id in plugin_ids])  # type: ignore
            all_plugins[required_optional] = plugins

        return all_plugins

    def post(self, request, *args, **kwargs):
        selected_plugins = request.POST.getlist("plugin", [])

        if not selected_plugins:
            messages.error(request, _("Please select a plugin to proceed."))
            return self.get(request, *args, **kwargs)
        for plugin_id in self.plugins["required"]:
            if plugin_id not in selected_plugins:
                messages.error(request, _("Please select all required plugins to proceed."))
                return self.get(request, *args, **kwargs)
        for selected_plugin in selected_plugins:
            try:
                self.get_katalogus().enable_boefje_by_id(selected_plugin)
            except HTTPError:
                messages.error(
                    request,
                    _("An error occurred while enabling {}. The plugin is not available.").format(selected_plugin),
                )
                return self.get(request, *args, **kwargs)
        messages.success(request, _("Plugins successfully enabled."))
        return redirect(
            reverse("step_9_choose_report_type", kwargs={"organization_code": self.organization.code})
            + get_selection(self.request)
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["plugins"] = self.get_plugins()
        return context


class OnboardingChooseReportTypeView(
    OrganizationPermissionRequiredMixin, IntroductionStepsMixin, OrganizationView, TemplateView
):
    """
    9. Choose a report type. Gives the user a choice of many report types. Ex. DNS report
    """

    template_name = "step_9_choose_report_type.html"
    current_step = 5
    permission_required = "tools.can_scan_organization"


class OnboardingCreateReportRecipe(
    OrganizationPermissionRequiredMixin,
    IntroductionStepsMixin,
    SingleOOIMixin,
    BaseReportView,
    SchedulerView,
    TemplateView,
):
    """
    9a. Shows the user object information, more in depth info about the object.
    """

    template_name = "step_9_choose_report_type.html"
    current_step = 5
    permission_required = "tools.can_scan_organization"
    task_type = "report"

    def post(self, request, *args, **kwargs):
        report_name_format = self.get_initial_report_name()
        parent_report_type = self.get_parent_report_type()
        report_recipe = self.create_report_recipe(report_name_format, parent_report_type, None)

        self.create_report_schedule(report_recipe, datetime.now(timezone.utc) + timedelta(minutes=2))
        run_findings_dashboard(self.organization)

        return redirect(
            reverse("step_10_report", kwargs={"organization_code": self.organization.code})
            + get_selection(self.request, {"recipe_id": report_recipe.primary_key})
        )

    def get_ooi_pks(self) -> list[str]:
        ooi = self.get_ooi(self.request.GET.get("ooi"))
        if ooi.web_url is not None:
            hostname_ooi = [Hostname(name=ooi.web_url.tokenized["netloc"]["name"], network=ooi.network)]
            return [hostname_ooi[0].primary_key]

        messages.error(self.request, _("Web URL not found."))
        logger.error("Web URL not found.")
        return []

    def get_report_type_ids(self) -> list[str]:
        return [self.request.POST.get("report_type", "")]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ooi"] = self.get_ooi(self.request.GET.get("ooi", ""))
        return context


class OnboardingReportView(
    OrganizationPermissionRequiredMixin, IntroductionStepsMixin, SingleOOIMixin, BaseReportView, TemplateView
):
    """
    10. The user already started the scan and is now waiting till scans are finished to generate the report.
    Onboarding finished and member onboarded, next step will be the actual report.
    """

    template_name = "step_10_report.html"
    current_step = 6
    permission_required = "tools.can_scan_organization"

    def post(self, request, *args, **kwargs):
        self.set_member_onboarded()

        messages.success(
            self.request,
            _(
                "Your report is scheduled for generation in about 3 minutes, "
                "as we are waiting for Boefjes to complete. "
                "In the meantime get familiar with OpenKAT and visit the Reports History tab later."
            ),
        )
        return redirect(reverse("report_history", kwargs={"organization_code": self.organization.code}))

    def set_member_onboarded(self):
        member = OrganizationMember.objects.get(user=self.request.user, organization=self.organization)
        member.onboarded = True
        member.status = OrganizationMember.STATUSES.ACTIVE
        member.save()


class CompleteOnboarding(OrganizationView):
    """
    Complete onboarding for redteamers and superusers.
    """

    def get(self, request, *args, **kwargs):
        self.organization_member.onboarded = True
        self.organization_member.status = OrganizationMember.STATUSES.ACTIVE
        self.organization_member.save()
        return redirect(reverse("crisis_room"))
