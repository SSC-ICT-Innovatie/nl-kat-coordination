from datetime import datetime, timedelta, timezone
from typing import Any

from account.forms import MemberRegistrationForm, OnboardingOrganizationUpdateForm, OrganizationForm
from account.mixins import OrganizationPermissionRequiredMixin, OrganizationView
from account.views import OOIClearanceMixin
from crisis_room.management.commands.dashboards import run_findings_dashboard
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.urls.base import reverse
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from django.views.generic.edit import CreateView, FormView, UpdateView
from httpx import HTTPError
from katalogus.client import Plugin
from reports.report_types.definitions import ReportPlugins
from reports.report_types.dns_report.report import DNSReport
from reports.views.base import BaseReportView, get_selection
from tools.models import GROUP_ADMIN, GROUP_CLIENT, GROUP_REDTEAM, Organization, OrganizationMember
from tools.ooi_helpers import get_or_create_ooi
from tools.view_helpers import Breadcrumb

from octopoes.models import OOI, Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network
from octopoes.models.ooi.web import URL
from onboarding.forms import OnboardingCreateObjectURLForm, OnboardingSetClearanceLevelForm
from onboarding.view_helpers import (
    DNS_REPORT_LEAST_CLEARANCE_LEVEL,
    ONBOARDING_PERMISSIONS,
    IntroductionAdminStepsMixin,
    IntroductionRegistrationStepsMixin,
    IntroductionStepsMixin,
    OnboardingBreadcrumbsMixin,
    RegistrationBreadcrumbsMixin,
)
from rocky.exceptions import RockyError
from rocky.messaging import clearance_level_warning_dns_report
from rocky.views.indemnification_add import IndemnificationAddView
from rocky.views.ooi_view import SingleOOIMixin, SingleOOITreeMixin
from rocky.views.scheduler import SchedulerView

User = get_user_model()


class OnboardingStart(OrganizationView):
    def get(self, request, *args, **kwargs):
        if request.user.is_superuser:
            return redirect("step_introduction_registration")
        if self.organization_member.has_perms(ONBOARDING_PERMISSIONS):
            return redirect("step_introduction", kwargs={"organization_code": self.organization.code})
        return redirect("crisis_room")


# REDTEAMER FLOW


class OnboardingIntroductionView(
    OrganizationPermissionRequiredMixin, IntroductionStepsMixin, OrganizationView, TemplateView
):
    """
    1. Start the onboarding wizard. What is OpenKAT and what it does.
    """

    template_name = "step_1_introduction.html"
    current_step = 1
    permission_required = "tools.can_scan_organization"


class OnboardingChooseReportInfoView(
    OrganizationPermissionRequiredMixin, IntroductionStepsMixin, OrganizationView, TemplateView
):
    """
    2. Introduction into reporting. All the necessities to generate a report.
    """

    template_name = "step_2a_choose_report_info.html"
    current_step = 2
    permission_required = "tools.can_scan_organization"


class OnboardingChooseReportTypeView(
    OrganizationPermissionRequiredMixin, IntroductionStepsMixin, OrganizationView, TemplateView
):
    """
    3. Choose a report type. Gives the user a choice of many report types. Ex. DNS report
    """

    template_name = "step_2b_choose_report_type.html"
    current_step = 2
    permission_required = "tools.can_scan_organization"


class OnboardingSetupScanOOIInfoView(
    OrganizationPermissionRequiredMixin, IntroductionStepsMixin, OrganizationView, TemplateView
):
    """
    4. Explanation that an object is needed to make scans.
    """

    template_name = "step_3a_setup_scan_ooi_info.html"
    current_step = 3
    permission_required = "tools.can_scan_organization"


class OnboardingSetupScanOOIAddView(
    OrganizationPermissionRequiredMixin, IntroductionStepsMixin, SingleOOITreeMixin, FormView
):
    """
    5. The user will create a URL object. Shows a form and validation to create object.
    """

    template_name = "step_3b_setup_scan_ooi_add.html"
    current_step = 3
    permission_required = "tools.can_scan_organization"
    form_class = OnboardingCreateObjectURLForm

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.report_type = self.request.GET.get("report_type", "")

    def get_or_create_url_object(self, url: str) -> OOI:
        network = Network(name="internet")
        url = URL(network=network.reference, raw=url, user_id=self.request.user.id)
        observed_at = datetime.now(timezone.utc)
        url_ooi, _ = get_or_create_ooi(self.octopoes_api_connector, self.bytes_client, url, observed_at)
        return url_ooi

    def form_valid(self, form):
        cleaned_url = form.cleaned_data["url"]
        ooi = self.get_or_create_url_object(cleaned_url)
        selection = {"ooi": ooi.primary_key, "report_type": self.report_type}
        return redirect(
            reverse("step_clearance_level_introduction", kwargs={"organization_code": self.organization.code})
            + get_selection(self.request, selection)
        )

    def build_breadcrumbs(self) -> list[Breadcrumb]:
        return super().build_breadcrumbs() + [
            {
                "url": reverse("ooi_add_type_select", kwargs={"organization_code": self.organization.code})
                + get_selection(self.request),
                "text": _("Creating an object"),
            }
        ]


class OnboardingClearanceLevelIntroductionView(
    OrganizationPermissionRequiredMixin,
    IntroductionStepsMixin,
    OnboardingBreadcrumbsMixin,
    OrganizationView,
    TemplateView,
):
    """
    6. Explanation what clearance levels mean.
    """

    template_name = "step_3d_clearance_level_introduction.html"
    permission_required = "tools.can_set_clearance_level"
    current_step = 3

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


class OnboardingAcknowledgeClearanceLevelView(
    OrganizationPermissionRequiredMixin,
    IntroductionStepsMixin,
    OnboardingBreadcrumbsMixin,
    OOIClearanceMixin,
    OrganizationView,
    TemplateView,
):
    """
    7. Explains the user that before setting a clearance level, they must have a permissiom to do so.
    Here they acknowledge the clearance level assigned by their administrator.
    """

    template_name = "step_3e_trusted_acknowledge_clearance_level.html"
    permission_required = "tools.can_set_clearance_level"
    current_step = 3

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ooi"] = self.request.GET.get("ooi", "")
        context["dns_report_least_clearance_level"] = DNS_REPORT_LEAST_CLEARANCE_LEVEL
        return context


class OnboardingSetClearanceLevelView(
    OrganizationPermissionRequiredMixin,
    IntroductionStepsMixin,
    OnboardingBreadcrumbsMixin,
    SingleOOITreeMixin,
    FormView,
):
    """
    8. Set the actual clearance level on the object created before.
    """

    template_name = "step_3f_set_clearance_level.html"
    permission_required = "tools.can_set_clearance_level"
    current_step = 3
    form_class = OnboardingSetClearanceLevelForm
    initial = {"level": DNS_REPORT_LEAST_CLEARANCE_LEVEL}

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.url = self.request.GET.get("ooi", "")
        self.report_type = self.request.GET.get("report_type", "")
        self.selection = {"ooi": self.url, "report_type": self.report_type}

    def form_valid(self, form):
        ooi = self.get_ooi(self.url)
        if not self.can_raise_clearance_level(ooi, DNS_REPORT_LEAST_CLEARANCE_LEVEL):
            return self.get(self.request, self.args, self.kwargs)
        return redirect(
            reverse("step_setup_scan_select_plugins", kwargs={"organization_code": self.organization.code})
            + get_selection(self.request, self.selection)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ooi"] = self.url
        context["dns_report_least_clearance_level"] = DNS_REPORT_LEAST_CLEARANCE_LEVEL
        return context


class OnboardingSetupScanSelectPluginsView(
    OrganizationPermissionRequiredMixin, IntroductionStepsMixin, OrganizationView, TemplateView
):
    """
    9. Shows the user all required and optional plugins to select from. Required plugins are mandatory to continue.
    """

    template_name = "step_3g_setup_scan_select_plugins.html"
    permission_required = "tools.can_enable_disable_boefje"
    current_step = 3
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
            reverse("step_setup_scan_ooi_detail", kwargs={"organization_code": self.organization.code})
            + get_selection(self.request)
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["plugins"] = self.get_plugins()
        return context


class OnboardingSetupScanOOIDetailView(
    OrganizationPermissionRequiredMixin,
    IntroductionStepsMixin,
    OnboardingBreadcrumbsMixin,
    SingleOOIMixin,
    BaseReportView,
    SchedulerView,
    TemplateView,
):
    """
    9. Shows the user object information, more in depth info about the object.
    """

    template_name = "step_3c_setup_scan_ooi_detail.html"
    current_step = 3
    permission_required = "tools.can_scan_organization"
    task_type = "report"

    def post(self, request, *args, **kwargs):
        report_name_format = self.get_initial_report_name()
        parent_report_type = self.get_parent_report_type()
        report_recipe = self.create_report_recipe(report_name_format, parent_report_type, None)

        self.create_report_schedule(report_recipe, datetime.now(timezone.utc) + timedelta(minutes=2))
        run_findings_dashboard(self.organization)

        return redirect(
            reverse("step_report", kwargs={"organization_code": self.organization.code})
            + get_selection(self.request, {"recipe_id": report_recipe.primary_key})
        )

    def get_ooi_pks(self) -> list[str]:
        ooi = self.get_ooi(self.request.GET.get("ooi", ""))
        hostname_ooi = [Hostname(name=ooi.web_url.tokenized["netloc"]["name"], network=ooi.network)]
        return [hostname_ooi[0].primary_key]

    def get_report_type_ids(self) -> list[str]:
        return [self.request.GET.get("report_type", "")]

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

    template_name = "step_4_report.html"
    current_step = 4
    permission_required = "tools.can_scan_organization"

    def post(self, request, *args, **kwargs):
        self.set_member_onboarded()

        recipe_id = request.GET.get("recipe_id", "")

        if recipe_id:
            reports = self.octopoes_api_connector.query(
                "ReportRecipe.<report_recipe[is Report]",
                valid_time=datetime.now(timezone.utc),
                source=Reference.from_str(recipe_id),
            )

            if reports:
                asset_reports = reports[0].input_oois
                return redirect(
                    reverse("view_report", kwargs={"organization_code": self.organization.code})
                    + "?"
                    + urlencode({"asset_report_id": asset_reports[0]})
                )
        return redirect(reverse("scheduled_reports", kwargs={"organization_code": self.organization.code}))

    def set_member_onboarded(self):
        member = OrganizationMember.objects.get(user=self.request.user, organization=self.organization)
        member.onboarded = True
        member.status = OrganizationMember.STATUSES.ACTIVE
        member.save()


# account flow


class OnboardingIntroductionRegistrationView(PermissionRequiredMixin, IntroductionRegistrationStepsMixin, TemplateView):
    """
    Step: 1 - Registration introduction
    """

    template_name = "account/step_1_registration_intro.html"
    current_step = 1
    permission_required = "tools.add_organizationmember"


class OnboardingOrganizationSetupView(PermissionRequiredMixin, IntroductionRegistrationStepsMixin, CreateView):
    """
    Step 2: Create a new organization
    """

    model = Organization
    template_name = "account/step_2a_organization_setup.html"
    form_class = OrganizationForm
    current_step = 2
    permission_required = "tools.add_organization"

    def get(self, request, *args, **kwargs):
        if member := OrganizationMember.objects.filter(user=self.request.user).first():
            return redirect(reverse("step_organization_update", kwargs={"organization_code": member.organization.code}))
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except RockyError as e:
            messages.add_message(request, messages.ERROR, str(e))

        return self.get(request, *args, **kwargs)

    def get_success_url(self) -> str:
        self.create_first_member(self.object)
        return reverse_lazy("step_indemnification_setup", kwargs={"organization_code": self.object.code})

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
    OrganizationPermissionRequiredMixin, IntroductionAdminStepsMixin, OrganizationView, UpdateView
):
    """
    Step 2: Update an existing organization (only name not code)
    """

    model = Organization
    template_name = "account/step_2a_organization_update.html"
    form_class = OnboardingOrganizationUpdateForm
    current_step = 2
    permission_required = "tools.change_organization"

    def get_object(self, queryset=None):
        return self.organization

    def get_success_url(self) -> str:
        return reverse_lazy("step_indemnification_setup", kwargs={"organization_code": self.organization.code})

    def form_valid(self, form):
        org_name = form.cleaned_data["name"]
        self.add_success_notification(org_name)
        return super().form_valid(form)

    def add_success_notification(self, org_name):
        success_message = _("{org_name} successfully updated.").format(org_name=org_name)
        messages.add_message(self.request, messages.SUCCESS, success_message)


class OnboardingIndemnificationSetupView(IntroductionAdminStepsMixin, IndemnificationAddView):
    """
    Step 3: Agree to idemnification to scan oois
    """

    current_step = 3
    template_name = "account/step_2b_indemnification_setup.html"

    def get_success_url(self) -> str:
        return reverse_lazy("step_account_setup_intro", kwargs={"organization_code": self.organization.code})


class OnboardingAccountSetupIntroView(
    OrganizationPermissionRequiredMixin, IntroductionAdminStepsMixin, OrganizationView, TemplateView
):
    """
    Step 4: Split flow to or continue with single account or continue to multiple account creation
    """

    template_name = "account/step_2c_account_setup_intro.html"
    current_step = 4
    permission_required = "tools.add_organizationmember"


class OnboardingAccountCreationMixin(
    OrganizationPermissionRequiredMixin, IntroductionAdminStepsMixin, OrganizationView, FormView
):
    account_type: str | None = None
    permission_required = "tools.add_organizationmember"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.organization
        kwargs["account_type"] = self.account_type
        return kwargs


# Account setup for multiple user accounts: redteam, admins, clients


class OnboardingChooseUserTypeView(
    OrganizationPermissionRequiredMixin, IntroductionAdminStepsMixin, OrganizationView, TemplateView
):
    """
    Step 1: Introduction about how to create multiple user accounts
    """

    current_step = 4
    template_name = "account/step_3_account_user_type.html"
    permission_required = "tools.add_organizationmember"


class OnboardingAccountSetupAdminView(RegistrationBreadcrumbsMixin, OnboardingAccountCreationMixin):
    """
    Step 1: Create an admin account with admin rights
    """

    template_name = "account/step_4_account_setup_admin.html"
    form_class = MemberRegistrationForm
    current_step = 4
    account_type = GROUP_ADMIN

    def get_success_url(self) -> str:
        return reverse_lazy("step_account_setup_red_teamer", kwargs={"organization_code": self.organization.code})

    def form_valid(self, form):
        name = form.cleaned_data["name"]
        self.add_success_notification(name)
        return super().form_valid(form)

    def add_success_notification(self, name):
        success_message = _("{name} successfully created.").format(name=name)
        messages.add_message(self.request, messages.SUCCESS, success_message)


class OnboardingAccountSetupRedTeamerView(RegistrationBreadcrumbsMixin, OnboardingAccountCreationMixin):
    """
    Step 2: Create an redteamer account with redteam rights
    """

    template_name = "account/step_5_account_setup_red_teamer.html"
    form_class = MemberRegistrationForm
    current_step = 4
    account_type = GROUP_REDTEAM

    def get_success_url(self, **kwargs):
        return reverse_lazy("step_account_setup_client", kwargs={"organization_code": self.organization.code})

    def form_valid(self, form):
        name = form.cleaned_data["name"]
        trusted_clearance_level = form.cleaned_data.get("trusted_clearance_level")
        if trusted_clearance_level and int(trusted_clearance_level) < DNS_REPORT_LEAST_CLEARANCE_LEVEL:
            clearance_level_warning_dns_report(self.request, trusted_clearance_level)
        self.add_success_notification(name)
        return super().form_valid(form)

    def add_success_notification(self, name):
        success_message = _("{name} successfully created.").format(name=name)
        messages.add_message(self.request, messages.SUCCESS, success_message)


class OnboardingAccountSetupClientView(RegistrationBreadcrumbsMixin, OnboardingAccountCreationMixin):
    """
    Step 3: Create a client account.
    """

    template_name = "account/step_6_account_setup_client.html"
    form_class = MemberRegistrationForm
    current_step = 4
    account_type = GROUP_CLIENT

    def get_success_url(self, **kwargs):
        return reverse_lazy("complete_onboarding", kwargs={"organization_code": self.organization.code})

    def form_valid(self, form):
        name = form.cleaned_data["name"]
        self.add_success_notification(name)
        return super().form_valid(form)

    def add_success_notification(self, name):
        success_message = _("{name} successfully created.").format(name=name)
        messages.add_message(self.request, messages.SUCCESS, success_message)


class CompleteOnboarding(OrganizationView):
    """
    Complete onboarding for redteamers and superusers.
    """

    def get(self, request, *args, **kwargs):
        self.organization_member.onboarded = True
        self.organization_member.status = OrganizationMember.STATUSES.ACTIVE
        self.organization_member.save()
        return redirect(reverse("crisis_room"))
