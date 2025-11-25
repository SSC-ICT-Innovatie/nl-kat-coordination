from datetime import UTC, datetime

import django_filters
import recurrence
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView, DetailView
from django_filters.views import FilterView

from objects.models import FindingType
from openkat.mixins import OrganizationFilterMixin
from openkat.models import Organization
from reports.models import Report
from tasks.models import ObjectSet, Schedule
from tasks.tasks import run_report_task


class ReportFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(label="Name", lookup_expr="icontains")
    scheduled = django_filters.BooleanFilter(label="Scheduled", method="filter_scheduled")

    class Meta:
        model = Report
        fields = ["name", "scheduled"]

    def filter_scheduled(self, queryset, name, value):
        """Filter reports by whether they have an associated schedule"""
        if value is True:
            # Reports that have a schedule (via file -> task_result -> task -> schedule)
            return queryset.filter(file__task_result__task__schedule__isnull=False)
        elif value is False:
            # Reports that don't have a schedule
            return queryset.filter(file__task_result__task__schedule__isnull=True)
        return queryset


class ReportListView(OrganizationFilterMixin, FilterView):
    template_name = "reports/report_list.html"
    model = Report
    ordering = ["-created_at"]
    paginate_by = settings.VIEW_DEFAULT_PAGE_SIZE
    filterset_class = ReportFilter

    def get_queryset(self):
        qs = super().get_queryset()

        if not self.request.user.can_access_all_organizations:
            # Filter reports by user's accessible organizations
            user_orgs = Organization.objects.filter(members__user=self.request.user)
            qs = qs.filter(organizations__in=user_orgs).distinct()

        # Optimize query to fetch schedule information
        qs = qs.select_related("file__task_result__task__schedule")

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [{"url": reverse("report_list"), "text": _("Reports")}]
        return context


class ReportDetailView(OrganizationFilterMixin, DetailView):
    template_name = "reports/report_detail.html"
    model = Report

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"url": reverse("report_list"), "text": _("Reports")},
            {"url": reverse("report_detail", kwargs={"pk": self.object.pk}), "text": self.object.name},
        ]
        return context


class ReportHTMLView(OrganizationFilterMixin, DetailView):
    template_name = "reports/report_html.html"
    model = Report

    def get_queryset(self):
        qs = super().get_queryset()

        if not self.request.user.can_access_all_organizations:
            # Filter reports by user's accessible organizations
            user_orgs = Organization.objects.filter(members__user=self.request.user)
            qs = qs.filter(organizations__in=user_orgs).distinct()

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report_data = self.object.data if self.object.data else {}

        context.update(report_data)
        context["generated_at"] = datetime.fromisoformat(context["generated_at"])

        context["breadcrumbs"] = [
            {"url": reverse("report_list"), "text": _("Reports")},
            {"url": reverse("report_detail", kwargs={"pk": self.object.pk}), "text": self.object.name},
            {"url": reverse("report_html", kwargs={"pk": self.object.pk}), "text": _("HTML View")},
        ]
        context["base_template"] = "layouts/base.html"
        context["is_pdf"] = False

        return context


class ReportCreateForm(forms.Form):
    name = forms.CharField(max_length=255, required=True, label=_("Report name"))
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False, label=_("Description"))

    GENERATION_CHOICES = [("now", _("Generate now")), ("schedule", _("Schedule report"))]
    generation_type = forms.ChoiceField(
        choices=GENERATION_CHOICES,
        initial="now",
        widget=forms.RadioSelect,
        label=_("When to generate"),
        help_text=_("Generate the report immediately or schedule it to run periodically"),
    )

    organizations = forms.ModelMultipleChoiceField(
        queryset=Organization.objects.none(),
        required=False,
        label=_("Organizations"),
        help_text=_(
            "Select organizations. For scheduled reports, a separate schedule will be created for each organization. "
            "Leave empty to include all organizations."
        ),
    )
    finding_types = forms.MultipleChoiceField(required=False, label=_("Finding types"))
    object_set = forms.ModelChoiceField(queryset=ObjectSet.objects.none(), required=False, label=_("Object set"))

    def __init__(self, *args, **kwargs):
        # Remove 'instance' if passed (CreateView passes it but Form doesn't accept it)
        kwargs.pop("instance", None)
        super().__init__(*args, **kwargs)

        try:
            self.fields["organizations"].queryset = Organization.objects.all()
        except Exception:
            self.fields["organizations"].queryset = Organization.objects.none()

        try:
            self.fields["object_set"].queryset = ObjectSet.objects.all()
        except Exception:
            self.fields["object_set"].queryset = ObjectSet.objects.none()

        try:
            finding_type_choices = [
                (ft.code, f"{ft.name or ft.code} ({ft.code})")
                for ft in FindingType.objects.all().order_by("name")
                if ft.code
            ]
            self.fields["finding_types"].choices = finding_type_choices
        except Exception:
            # If we can't fetch finding types, leave the field empty
            self.fields["finding_types"].choices = []
            self.fields[
                "finding_types"
            ].help_text = "Finding types could not be loaded. Please check your database connection."


class ReportCreateView(PermissionRequiredMixin, CreateView):
    template_name = "reports/report_form.html"
    form_class = ReportCreateForm
    permission_required = "reports.add_report"

    def form_valid(self, form):
        name = form.cleaned_data["name"]
        description = form.cleaned_data["description"]
        generation_type = form.cleaned_data["generation_type"]
        finding_types = form.cleaned_data["finding_types"]
        object_set = form.cleaned_data["object_set"]

        if generation_type == "schedule":
            organizations = form.cleaned_data.get("organizations")
            schedules_to_create = []

            if organizations:
                for organization in organizations:
                    schedules_to_create.append({"organization": organization, "name_suffix": f" - {organization.name}"})
            else:
                schedules_to_create.append({"organization": None, "name_suffix": ""})

            created_schedules = []
            for schedule_info in schedules_to_create:
                schedule = Schedule.objects.create(
                    enabled=True,
                    recurrences=recurrence.Recurrence(
                        rrules=[recurrence.Rule(recurrence.DAILY)], dtstart=datetime.now(UTC)
                    ),
                    task_type="report",
                    organization=schedule_info["organization"],
                    object_set=object_set,
                    report_name=name + schedule_info["name_suffix"],
                    report_description=description,
                    report_finding_types=list(finding_types) if finding_types else [],
                )
                created_schedules.append(schedule)

            if len(created_schedules) == 1:
                messages.success(
                    self.request,
                    _(
                        "Report schedule created successfully. The report will be generated daily. "
                        "You can edit the schedule to change the recurrence."
                    ),
                )
                return redirect(reverse("schedule_detail", kwargs={"pk": created_schedules[0].pk}))
            else:
                messages.success(
                    self.request,
                    _(
                        f"Created {len(created_schedules)} report schedules (one per organization). "
                        f"Each will be generated daily. You can view them in the schedules list."
                    ),
                )
                return redirect(reverse("schedule_list"))
        else:
            organizations = form.cleaned_data["organizations"]
            organization_codes = [org.code for org in organizations] if organizations else []

            task = run_report_task(
                name=name,
                description=description,
                organization_codes=organization_codes,
                finding_types=list(finding_types) if finding_types else [],
                object_set_id=object_set.id if object_set else None,
            )

            messages.success(
                self.request,
                _(f"Report task created: {task.id}. You'll be able to download the report once it's completed."),
            )

            return redirect(self.get_success_url())

    def get_success_url(self):
        redirect_url = self.request.POST.get("current_url")

        if redirect_url and url_has_allowed_host_and_scheme(redirect_url, allowed_hosts=None):
            return redirect_url

        return reverse_lazy("report_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [{"url": reverse("report_list"), "text": _("Reports")}]
        return context


class ReportDownloadView(PermissionRequiredMixin, View):
    permission_required = "reports.view_report"

    def get(self, request, pk):
        report = Report.objects.get(pk=pk)

        if not request.user.can_access_all_organizations:
            user_orgs = Organization.objects.filter(members__user=request.user)
            if not report.organizations.filter(id__in=user_orgs.values_list("id", flat=True)).exists():
                raise Http404("Report not found or you don't have permission to access it")

        if report.file and report.file.file:
            response = FileResponse(report.file.file.open("rb"), content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="{report.name}.pdf"'
            return response


class ReportDataDownloadView(PermissionRequiredMixin, View):
    permission_required = "reports.view_report"

    def get(self, request, pk):
        report = Report.objects.get(pk=pk)

        if not request.user.can_access_all_organizations:
            user_orgs = Organization.objects.filter(members__user=request.user)
            if not report.organizations.filter(id__in=user_orgs.values_list("id", flat=True)).exists():
                raise Http404("Report not found or you don't have permission to access it")

        response = JsonResponse(report.data, safe=False, json_dumps_params={"indent": 2})
        response["Content-Disposition"] = f'attachment; filename="{report.name}_data.json"'
        return response
