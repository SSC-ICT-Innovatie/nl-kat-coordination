from typing import Any

import structlog
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.urls.base import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from django.views.generic.edit import CreateView, FormView, UpdateView

from onboarding.view_helpers import (
    DNS_REPORT_LEAST_CLEARANCE_LEVEL,
    ONBOARDING_PERMISSIONS,
    IntroductionAdminStepsMixin,
    IntroductionRegistrationStepsMixin,
    IntroductionStepsMixin,
    OnboardingBreadcrumbsMixin,
    RegistrationBreadcrumbsMixin,
)
from openkat.exceptions import OpenKATError
from openkat.forms import MemberRegistrationForm, OnboardingOrganizationUpdateForm, OrganizationForm
from openkat.mixins import OrganizationPermissionRequiredMixin, OrganizationView
from openkat.models import GROUP_ADMIN, GROUP_READ_ONLY, Organization, OrganizationMember
from openkat.views.account import ObjectClearanceMixin
from openkat.views.indemnification_add import IndemnificationAddView

logger = structlog.get_logger(__name__)


class OnboardingStart(OrganizationView):
    def get(self, request, *args, **kwargs):
        if request.user.is_superuser:
            return redirect("step_introduction_registration")
        if self.organization_member.has_perms(ONBOARDING_PERMISSIONS):
            return redirect("step_introduction", kwargs={"organization_code": self.organization.code})
        return redirect("plugin_list")


class OnboardingIntroductionView(
    OrganizationPermissionRequiredMixin, IntroductionStepsMixin, OrganizationView, TemplateView
):
    """1. Start the onboarding wizard. What is OpenKAT and what it does."""

    template_name = "step_1_introduction.html"
    current_step = 1
    permission_required = "openkat.can_scan_organization"


class OnboardingChooseReportInfoView(
    OrganizationPermissionRequiredMixin, IntroductionStepsMixin, OrganizationView, TemplateView
):
    """2. Introduction into reporting. All the necessities to generate a report."""

    template_name = "step_2a_choose_report_info.html"
    current_step = 2
    permission_required = "openkat.can_scan_organization"


class OnboardingClearanceLevelIntroductionView(
    OrganizationPermissionRequiredMixin,
    IntroductionStepsMixin,
    OnboardingBreadcrumbsMixin,
    OrganizationView,
    TemplateView,
):
    """6. Explanation what clearance levels mean."""

    template_name = "step_3d_clearance_level_introduction.html"
    permission_required = "openkat.can_set_clearance_level"
    current_step = 3

    def get_boefjes_tiles(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "dns",
                "type": "plugin",
                "scan_level": "1",
                "name": "DNS",
                "description": _("Query the dns records of a hostname"),
                "enabled": False,
            }
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object"] = self.request.GET.get("object", "")
        context["plugins"] = self.get_boefjes_tiles()
        return context


class OnboardingAcknowledgeClearanceLevelView(
    OrganizationPermissionRequiredMixin,
    IntroductionStepsMixin,
    OnboardingBreadcrumbsMixin,
    ObjectClearanceMixin,
    OrganizationView,
    TemplateView,
):
    """
    7. Explains the user that before setting a clearance level, they must have a permission to do so.
    Here they acknowledge the clearance level assigned by their administrator.
    """

    template_name = "step_3e_trusted_acknowledge_clearance_level.html"
    permission_required = "openkat.can_set_clearance_level"
    current_step = 3

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object"] = self.request.GET.get("object", "")
        context["dns_report_least_clearance_level"] = DNS_REPORT_LEAST_CLEARANCE_LEVEL
        return context


class OnboardingIntroductionRegistrationView(PermissionRequiredMixin, IntroductionRegistrationStepsMixin, TemplateView):
    """
    Step: 1 - Registration introduction
    """

    template_name = "account/step_1_registration_intro.html"
    current_step = 1
    permission_required = "openkat.add_organizationmember"


class OnboardingOrganizationSetupView(PermissionRequiredMixin, IntroductionRegistrationStepsMixin, CreateView):
    """Step 2: Create a new organization"""

    model = Organization
    template_name = "account/step_2a_organization_setup.html"
    form_class = OrganizationForm
    current_step = 2
    permission_required = "openkat.add_organization"

    object: Organization | None

    def get(self, request, *args, **kwargs):
        if member := OrganizationMember.objects.filter(user=self.request.user).first():
            return redirect(reverse("step_organization_update", kwargs={"organization_code": member.organization.code}))
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except OpenKATError as e:
            logger.exception("Failed to create organization")
            messages.add_message(request, messages.ERROR, str(e))

        return self.get(request, *args, **kwargs)

    def get_success_url(self) -> str:
        if self.object:
            self.create_first_member(self.object)
            return reverse_lazy("step_indemnification_setup", kwargs={"organization_code": self.object.code})

        raise Organization.DoesNotExist

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
    """Step 2: Update an existing organization (only name not code)"""

    model = Organization
    template_name = "account/step_2a_organization_update.html"
    form_class = OnboardingOrganizationUpdateForm
    current_step = 2
    permission_required = "openkat.change_organization"

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
    """Step 3: Agree to idemnification to scan objects"""

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
    permission_required = "openkat.add_organizationmember"


class OnboardingAccountCreationMixin(
    OrganizationPermissionRequiredMixin, IntroductionAdminStepsMixin, OrganizationView, FormView
):
    account_type: str | None = None
    permission_required = "openkat.add_organizationmember"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.organization
        kwargs["account_type"] = self.account_type
        return kwargs


class OnboardingChooseUserTypeView(
    OrganizationPermissionRequiredMixin, IntroductionAdminStepsMixin, OrganizationView, TemplateView
):
    """
    Step 1: Introduction about how to create multiple user accounts
    """

    current_step = 4
    template_name = "account/step_3_account_user_type.html"
    permission_required = "openkat.add_organizationmember"


class OnboardingAccountSetupAdminView(RegistrationBreadcrumbsMixin, OnboardingAccountCreationMixin):
    """
    Step 1: Create an admin account with admin rights
    """

    template_name = "account/step_4_account_setup_admin.html"
    form_class = MemberRegistrationForm
    current_step = 4
    account_type = GROUP_ADMIN

    def get_success_url(self) -> str:
        return reverse_lazy("step_account_setup_client", kwargs={"organization_code": self.organization.code})

    def form_valid(self, form):
        name = form.cleaned_data["name"]
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
    account_type = GROUP_READ_ONLY

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
    Complete onboarding for superusers.
    """

    def get(self, request, *args, **kwargs):
        return redirect(reverse("plugin_list"))
