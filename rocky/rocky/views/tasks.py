from collections.abc import Iterable
from typing import Any

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic.list import ListView
from httpx import HTTPError
from tools.forms.scheduler import TaskFilterForm

from rocky.paginator import RockyPaginator
from rocky.scheduler import LazyTaskList, SchedulerError, scheduler_client
from rocky.views.page_actions import PageActionsView
from rocky.views.scheduler import SchedulerView, UnboundSchedulerView


class SchedulerListView(ListView):
    object_list: Iterable[Any]

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        try:
            return super().dispatch(request, *args, **kwargs)
        except SchedulerError as error:
            messages.error(request, error.message)
            self.object_list = []
            return self.render_to_response(self.get_context_data())


class TaskListView(SchedulerView, SchedulerListView, PageActionsView):
    paginator_class = RockyPaginator
    paginate_by = 150
    context_object_name = "task_list"

    def get_queryset(self):
        return self.get_task_list()

    def post(self, request, *args, **kwargs):
        if self.action == self.RESCHEDULE_TASK:
            task_id = self.request.POST.get("task_id", "")
            self.reschedule_task(task_id)

        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["task_filter_form"] = self.get_task_filter_form()
        context["active_filters_counter"] = self.count_active_task_filters()
        first_page = True

        page_obj = context.get("page_obj")

        if page_obj:
            # Explicitly check if this is the first page
            first_page = page_obj.number == 1

        if context["active_filters_counter"] == 0 and first_page:
            context["stats"] = self.get_task_statistics()
        context["breadcrumbs"] = [
            {"url": reverse("task_list", kwargs={"organization_code": self.organization.code}), "text": _("Tasks")}
        ]
        return context


class OOIDetailTaskListView(TaskListView):
    paginate_by = 20


class BoefjesTaskListView(TaskListView):
    template_name = "tasks/boefjes.html"
    task_type = "boefje"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"url": reverse("task_list", kwargs={"organization_code": self.organization.code}), "text": _("Tasks")},
            {
                "url": reverse("boefjes_task_list", kwargs={"organization_code": self.organization.code}),
                "text": _("Boefjes"),
            },
        ]
        return context


class NormalizersTaskListView(TaskListView):
    template_name = "tasks/normalizers.html"
    task_type = "normalizer"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"url": reverse("task_list", kwargs={"organization_code": self.organization.code}), "text": _("Tasks")},
            {
                "url": reverse("normalizers_task_list", kwargs={"organization_code": self.organization.code}),
                "text": _("Normalizers"),
            },
        ]

        # Search for the corresponding Normalizer names and add those to the task_list
        task_list = context.get("task_list", [])
        ids = {
            task.data.raw_data.boefje_meta.boefje.id
            for task in task_list
            if task.data.raw_data.boefje_meta.boefje.id != "manual"
        }
        plugins = self.katalogus_client.get_plugins(ids=list(ids))
        plugin_dict = {p.id: p.name for p in plugins}

        for task in task_list:
            boefje_id = task.data.raw_data.boefje_meta.boefje.id
            task.data.raw_data.boefje_meta.boefje.name = plugin_dict[boefje_id] if boefje_id != "manual" else "Manual"

        return context


class ReportsTaskListView(TaskListView):
    template_name = "tasks/reports.html"
    task_type = "report"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"url": reverse("task_list", kwargs={"organization_code": self.organization.code}), "text": _("Tasks")},
            {
                "url": reverse("reports_task_list", kwargs={"organization_code": self.organization.code}),
                "text": _("Reports"),
            },
        ]
        return context


class AllTaskListView(UnboundSchedulerView, SchedulerListView, PageActionsView):
    paginator_class = RockyPaginator
    paginate_by = 150
    context_object_name = "task_list"
    client = scheduler_client(None)
    task_filter_form = TaskFilterForm

    def get_organizations_filter(self) -> dict[str, dict[str, list[dict[str, str | list[str]]]]]:
        if self.request.user.has_perm("tools.can_access_all_organizations"):
            # We don't need to add a filter if the user can access all organizations
            return {}

        return {
            "filters": {
                "filters": [{"column": "organisation", "operator": "in", "value": self.get_user_organizations()}]
            }
        }

    def get_queryset(self):
        form_data = self.get_task_filters()
        kwargs = {k: v for k, v in form_data.items() if v} | self.get_organizations_filter()

        try:
            return LazyTaskList(self.client, **kwargs)

        except HTTPError as error:
            error_message = _(f"Fetching tasks failed: no connection with scheduler: {error}")
            messages.add_message(self.request, messages.ERROR, error_message)
            return []
        except SchedulerError as error:
            messages.add_message(self.request, messages.ERROR, str(error))
            return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["task_filter_form"] = self.get_task_filter_form()
        context["active_filters_counter"] = self.count_active_task_filters()
        first_page = True

        page_obj = context.get("page_obj")

        if page_obj:
            # Explicitly check if this is the first page
            first_page = page_obj.number == 1

        if context["active_filters_counter"] == 0 and first_page:
            task_organizations = (
                self.get_user_organizations()
                if not self.request.user.has_perm("tools.can_access_all_organizations")
                else None
            )
            context["stats"] = self.client.get_combined_schedulers_stats(self.get_task_type(), task_organizations)
        context["breadcrumbs"] = [{"url": reverse("all_task_list", kwargs={}), "text": _("All Tasks")}]
        return context


class AllBoefjesTaskListView(AllTaskListView):
    template_name = "tasks/boefjes.html"
    task_type = "boefje"


class AllNormalizersTaskListView(AllTaskListView):
    template_name = "tasks/normalizers.html"
    task_type = "normalizer"


class AllReportsTaskListView(AllTaskListView):
    template_name = "tasks/reports.html"
    task_type = "report"
