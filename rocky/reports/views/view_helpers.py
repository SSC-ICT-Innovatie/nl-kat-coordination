from datetime import datetime

from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from tools.models import Organization
from tools.view_helpers import StepsMixin

from reports.views.base import get_selection


class GenerateReportStepsMixin(StepsMixin):
    organization: Organization
    temporal_context: datetime | None

    def build_steps(self):
        selection = get_selection(self.request)
        steps = [
            {
                "text": _("1: Select objects"),
                "url": reverse_lazy(
                    "generate_report_select_oois",
                    kwargs={"organization_code": self.organization.code, "temporal_context": self.temporal_context},
                )
                + selection,
            },
            {
                "text": _("2: Choose report types"),
                "url": reverse_lazy(
                    "generate_report_select_report_types",
                    kwargs={"organization_code": self.organization.code, "temporal_context": self.temporal_context},
                )
                + selection,
            },
            {
                "text": _("3: Configuration"),
                "url": reverse_lazy(
                    "generate_report_setup_scan",
                    kwargs={"organization_code": self.organization.code, "temporal_context": self.temporal_context},
                )
                + selection,
            },
            {
                "text": _("4: Export setup"),
                "url": reverse_lazy(
                    "generate_report_export_setup",
                    kwargs={"organization_code": self.organization.code, "temporal_context": self.temporal_context},
                )
                + selection,
            },
        ]
        return steps


class AggregateReportStepsMixin(StepsMixin):
    organization: Organization
    temporal_context: datetime | None

    def build_steps(self):
        selection = get_selection(self.request)
        steps = [
            {
                "text": _("1: Select objects"),
                "url": reverse_lazy(
                    "aggregate_report_select_oois",
                    kwargs={"organization_code": self.organization.code, "temporal_context": self.temporal_context},
                )
                + selection,
            },
            {
                "text": _("2: Choose report types"),
                "url": reverse_lazy(
                    "aggregate_report_select_report_types",
                    kwargs={"organization_code": self.organization.code, "temporal_context": self.temporal_context},
                )
                + selection,
            },
            {
                "text": _("3: Configuration"),
                "url": reverse_lazy(
                    "aggregate_report_setup_scan",
                    kwargs={"organization_code": self.organization.code, "temporal_context": self.temporal_context},
                )
                + selection,
            },
            {
                "text": _("4: Export setup"),
                "url": reverse_lazy(
                    "aggregate_report_export_setup",
                    kwargs={"organization_code": self.organization.code, "temporal_context": self.temporal_context},
                )
                + selection,
            },
        ]
        return steps


class MultiReportStepsMixin(StepsMixin):
    organization: Organization
    temporal_context: datetime | None

    def build_steps(self, **kwargs):
        selection = get_selection(self.request)
        steps = [
            {
                "text": _("1: Select objects"),
                "url": reverse_lazy(
                    "multi_report_select_oois",
                    kwargs={"organization_code": self.organization.code, "temporal_context": self.temporal_context},
                )
                + selection,
            },
            {
                "text": _("2: Choose report types"),
                "url": reverse_lazy(
                    "multi_report_select_report_types",
                    kwargs={"organization_code": self.organization.code, "temporal_context": self.temporal_context},
                )
                + selection,
            },
            {
                "text": _("3: Export setup"),
                "url": reverse_lazy(
                    "multi_report_export_setup",
                    kwargs={"organization_code": self.organization.code, "temporal_context": self.temporal_context},
                )
                + selection,
            },
        ]
        return steps
