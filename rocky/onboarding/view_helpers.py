from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from reports.views.base import get_selection
from tools.models import Organization
from tools.view_helpers import StepsMixin

ONBOARDING_PERMISSIONS = (
    "tools.can_scan_organization",
    "tools.can_set_clearance_level",
    "tools.can_enable_disable_boefje",
)

DNS_REPORT_LEAST_CLEARANCE_LEVEL = 1


class IntroductionStepsMixin(StepsMixin):
    """Flow for redteamers/admins added to an organization as a member - needs the organization as a context."""

    organization: Organization

    def build_steps(self):
        steps = [
            {
                "text": _("1: Welcome"),
                "url": reverse_lazy("step_1a_introduction", kwargs={"organization_code": self.organization.code})
                + get_selection(self.request),
            },
            {
                "text": _("2: Organization setup"),
                "url": reverse_lazy("step_2b_organization_update", kwargs={"organization_code": self.organization.code})
                + get_selection(self.request),
            },
            {
                "text": _("3: Add object"),
                "url": reverse_lazy(
                    "step_5_add_scan_ooi", kwargs={"ooi_type": "URL", "organization_code": self.organization.code}
                )
                + get_selection(self.request),
            },
            {
                "text": _("4: Plugins"),
                "url": reverse_lazy("step_9_choose_report_type", kwargs={"organization_code": self.organization.code})
                + get_selection(self.request),
            },
            {
                "text": _("5: Generating report"),
                "url": reverse_lazy("step_10_report", kwargs={"organization_code": self.organization.code})
                + get_selection(self.request),
            },
        ]
        return steps


class IntroductionRegistrationStepsMixin(StepsMixin):
    """Flow for new superusers that need to create an organization as well."""

    organization: Organization

    def build_steps(self):
        steps = [
            {
                "text": _("1: Welcome"),
                "url": reverse_lazy("step_1_introduction_registration") + get_selection(self.request),
            },
            {
                "text": _("2: Organization setup"),
                "url": reverse_lazy("step_2a_organization_setup") + get_selection(self.request),
            },
            {"text": _("3: Add object"), "url": "" + get_selection(self.request)},
            {"text": _("4: Plugins"), "url": "" + get_selection(self.request)},
            {"text": _("5: Generating report"), "url": "" + get_selection(self.request)},
        ]
        return steps
