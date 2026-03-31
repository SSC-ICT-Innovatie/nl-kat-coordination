import uuid
from datetime import datetime, timedelta
from typing import Any

import structlog
from account.mixins import UnboundOrganizationView
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.utils.translation import gettext_lazy as _
from katalogus.client import Boefje, Normalizer
from reports.forms import (
    ReportNameForm,
    ReportRecurrenceChoiceForm,
    ReportScheduleStartDateChoiceForm,
    ReportScheduleStartDateForm,
)
from tools.forms.scheduler import OrganizationTaskFilterForm, TaskFilterForm

from octopoes.models import OOI
from octopoes.models.ooi.reports import ReportRecipe
from rocky.scheduler import Boefje as SchedulerBoefje
from rocky.scheduler import (
    BoefjeTask,
    LazyTaskList,
    NormalizerTask,
    RawData,
    ReportTask,
    ScheduleRequest,
    SchedulerError,
    ScheduleResponse,
    SchedulerTaskNotFound,
    Task,
    TaskPush,
    scheduler_client,
)
from rocky.scheduler import Normalizer as SchedulerNormalizer
from rocky.views.mixins import OctopoesView

logger = structlog.get_logger(__name__)


def get_date_time(date: str | None) -> datetime | None:
    if date:
        return datetime.strptime(date, "%Y-%m-%d")
    return None


class UnboundSchedulerView(UnboundOrganizationView):
    task_type: str
    task_filter_form = TaskFilterForm
    _form_instance = None

    report_schedule_form_start_date_choice = ReportScheduleStartDateChoiceForm  # today or different date
    report_schedule_form_start_date_time_recurrence = ReportScheduleStartDateForm  # date, time and recurrence

    report_schedule_form_recurrence_choice = ReportRecurrenceChoiceForm  # once or repeat

    report_name_form = ReportNameForm  # name format

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.scheduler_client = scheduler_client(None)
        self.scheduler_id = self.task_type

    def get_task_type(self):
        return self.task_type

    def get_plugin_specific_tasks_for_normalizers(self, plugin_id) -> list[dict[str, str]]:
        if plugin_id:
            return [
                {"column": "data", "field": f"{self.task_type}__id", "operator": "==", "value": plugin_id},
                {"column": "data", "field": "raw_data__boefje_meta__boefje__id", "operator": "==", "value": plugin_id},
            ]
        return []

    def get_plugin_specific_tasks_for_boefjes(self, plugin_id) -> dict[str, str]:
        if plugin_id:
            return {"column": "data", "field": f"{self.task_type}__id", "operator": "==", "value": plugin_id}
        return {}

    def get_ooi_search_specific_tasks(self, search) -> dict[str, str]:
        if search:
            return {"column": "data", "field": "input_ooi", "operator": "ilike", "value": f"%{search}%"}
        return {}

    def get_specific_tasks_by_id(self, task_id) -> dict[str, str]:
        if task_id:
            return {"column": "id", "operator": "==", "value": task_id}
        return {}

    def get_ooi_specific_tasks(self, ooi_id) -> dict[str, str]:
        if ooi_id:
            if self.task_type == "normalizer":
                return {
                    "column": "data",
                    "field": "raw_data__boefje_meta__input_ooi",
                    "operator": "==",
                    "value": ooi_id,
                }
            elif self.task_type == "boefje":
                return {"column": "data", "field": "input_ooi", "operator": "==", "value": ooi_id}
        return {}

    def get_task_filter_form_data(self) -> dict[str, Any]:
        form = self.get_task_filter_form()
        form.is_valid()
        return {k: v for k, v in form.cleaned_data.items() if v}

    def _build_task_filters(self, formdata: dict[str, Any], filters: dict[str, Any]) -> dict[str, Any]:
        plugin_id = formdata.get("plugin_id", self.plugin.id if hasattr(self, "plugin") else None)
        if plugin_id:
            if formdata.get("plugin_id", False):
                del formdata["plugin_id"]
            if self.task_type == "normalizer":
                filters["filters"]["or"] = self.get_plugin_specific_tasks_for_normalizers(plugin_id)
            elif self.task_type == "boefje":
                filters["filters"]["and"].append(self.get_plugin_specific_tasks_for_boefjes(plugin_id))

        ooi_id = formdata.get("ooi_id")
        if ooi_id:
            del formdata["ooi_id"]
            filters["filters"]["and"].append(self.get_ooi_specific_tasks(ooi_id))

        ooi_search = formdata.get("ooi_search")
        if ooi_search:
            del formdata["ooi_search"]
            filters["filters"]["and"].append(self.get_ooi_search_specific_tasks(ooi_search))

        task_id = formdata.get("task_id")
        if task_id:
            del formdata["task_id"]
            filters["filters"]["and"].append(self.get_specific_tasks_by_id(task_id))

        return filters

    def _init_filters(self, formdata: dict[str, Any]) -> dict[str, Any]:
        filters: dict[str, Any] = {"filters": {"and": []}}

        organizations = formdata.get("organizations")
        if organizations and organizations != [""]:
            filters = {"filters": {"and": [self.get_organization_specific_tasks(organizations)]}}
            del formdata["organizations"]

        return filters

    def get_task_filters(self) -> dict[str, Any]:
        formdata = self.get_task_filter_form_data()

        filters = self._init_filters(formdata)
        filters = self._build_task_filters(formdata, filters)

        return {"scheduler_id": self.scheduler_id, "task_type": self.task_type, "filters": filters, **formdata}

    def count_active_task_filters(self, subtract=None):
        if not subtract:
            subtract = ("observed_at",)
        form_data = self.get_task_filter_form_data()

        count = len(form_data)
        for task_filter in form_data:
            if task_filter in subtract:
                count -= 1
        return count

    def get_organization_specific_tasks(self, organizations: list[str] | None = None) -> dict[str, str | list[str]]:
        if organizations:
            return {"column": "organisation", "operator": "in", "value": organizations}
        return {}

    def get_task_filter_form(self) -> TaskFilterForm:
        if not self._form_instance:
            self._form_instance = self.task_filter_form(self.request.GET, organizations=self.get_user_organizations())
        return self._form_instance

    def get_task_list(self) -> LazyTaskList | list[Any]:
        try:
            return LazyTaskList(self.scheduler_client, **self.get_task_filters())
        except SchedulerError as error:
            messages.error(self.request, error.message)
        return []

    def get_report_schedule_form_start_date_choice(self):
        return self.report_schedule_form_start_date_choice(self.request.POST)

    def get_report_schedule_form_start_date_time_recurrence(self):
        return self.report_schedule_form_start_date_time_recurrence()

    def get_report_schedule_form_recurrence_choice(self):
        return self.report_schedule_form_recurrence_choice(self.request.POST)

    def get_report_name_form(self):
        return self.report_name_form()

    def get_task_details(self, task_id: str) -> Task | None:
        try:
            task = self.scheduler_client.get_task_details(task_id)
            if task.organization_id() not in self.get_user_organizations():
                raise SchedulerTaskNotFound()

            return task
        except SchedulerTaskNotFound:
            raise Http404()

    def get_task_statistics(self) -> dict[Any, Any]:
        try:
            return self.scheduler_client.get_task_stats(self.task_type)
        except SchedulerError as error:
            messages.error(self.request, error.message)
        return {}

    def get_output_oois(self, task):
        try:
            origins = self.octopoes_api_connector.list_origins(
                valid_time=task.modified_at + timedelta(seconds=1),  # we need to account for XTDB's sync time
                task_id=task.id,
            )
            for origin in origins:
                for ooi in origin.result:
                    yield str(ooi)
        except SchedulerError as error:
            messages.error(self.request, error.message)

    def get_json_task_details(self) -> JsonResponse:
        try:
            task = self.get_task_details(self.kwargs["task_id"])
            if task:
                params: dict[str, list[str] | str] = {"oois": list(self.get_output_oois(task))}
                if task.modified_at:
                    params["valid_time"] = task.modified_at.strftime("%Y-%m-%dT%H:%M:%S")
                return JsonResponse(params, safe=False)
            else:
                raise SchedulerTaskNotFound()

        except SchedulerTaskNotFound:
            raise Http404()

    def get_schedule_details(self, schedule_id: str) -> ScheduleResponse:
        try:
            return self.scheduler_client.get_schedule_details(schedule_id)
        except SchedulerError as error:
            return messages.error(self.request, error.message)

    def get_schedule_with_filters(self, filters: dict[str, list[dict[str, str]]]) -> ScheduleResponse | None:
        try:
            schedule = self.scheduler_client.post_schedule_search(filters)
            if schedule.results:
                return schedule.results[0]
        except SchedulerError as error:
            messages.error(self.request, error.message)
        return None

    def schedule_task(self, task: TaskPush) -> None:
        if not self.indemnification_present:
            return self.indemnification_error()
        try:
            self.scheduler_client.push_task(task)
        except SchedulerError as error:
            messages.error(self.request, error.message)
        else:
            messages.success(
                self.request,
                _(
                    "Your task is scheduled and will soon be started in the background. "
                    "Results will be added to the object list when they are in. "
                    "It may take some time, a refresh of the page may be needed to show the results."
                ),
            )

    # FIXME: Tasks should be (re)created with supplied data, not by fetching prior
    # task info from the scheduler. Task data should be available from the context
    # from which the task is created.
    def reschedule_task(self, task_id: str) -> None:
        try:
            task = self.get_task_details(task_id)
            if task:
                if task.organization_id() not in self.get_user_organizations():
                    raise SchedulerTaskNotFound()

                new_id = uuid.uuid4()
                task.data.id = new_id

                new_task = TaskPush(
                    id=new_id,
                    scheduler_id=task.scheduler_id,
                    organisation=task.organization_id(),
                    priority=1,
                    data=task.data.model_dump(),
                )

                self.schedule_task(new_task)
            else:
                raise SchedulerTaskNotFound()
        except SchedulerTaskNotFound:
            raise Http404()

    def convert_recurrence_to_cron_expressions(self, recurrence: str, start_date_time: datetime) -> str:
        """
        The user defines the start date and time.
        """

        if start_date_time and recurrence:
            day = start_date_time.day
            month = start_date_time.month
            week = start_date_time.strftime("%w").upper()  # ex. 4
            hour = start_date_time.hour
            minute = start_date_time.minute

            cron_expr = {
                "daily": f"{minute} {hour} * * *",  # Recurres every day at the selected time
                "weekly": f"{minute} {hour} * * {week}",  # Recurres every week on the {week} at the selected time
                "yearly": f"{minute} {hour} {day} {month} *",
                # Recurres every year on the {day} of the {month} at the selected time
            }

            if day >= 28:
                cron_expr["monthly"] = f"{minute} {hour} L * *"
            else:
                cron_expr["monthly"] = (
                    f"{minute} {hour} {day} * *"  # Recurres on the exact {day} of the month at the selected time
                )

            return cron_expr.get(recurrence, "")
        return ""


class SchedulerView(UnboundSchedulerView, OctopoesView):
    task_filter_form = OrganizationTaskFilterForm

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.scheduler_client.organization_code = self.organization.code

    def get_task_filter_form(self) -> TaskFilterForm:
        if not self._form_instance:
            self._form_instance = self.task_filter_form(self.request.GET)
        return self._form_instance

    def _init_filters(self, formdata: dict[str, Any]) -> dict[str, Any]:
        return {"filters": {"and": [self.get_organization_specific_tasks()]}}

    def create_report_schedule(self, report_recipe: ReportRecipe, deadline_at: datetime) -> ScheduleResponse | None:
        try:
            report_task = ReportTask(
                organisation_id=self.organization.code, report_recipe_id=str(report_recipe.recipe_id)
            ).model_dump()

            schedule_request = ScheduleRequest(
                scheduler_id=self.scheduler_id,
                organisation=self.organization.code,
                data=report_task,
                schedule=report_recipe.cron_expression,
                deadline_at=deadline_at.isoformat(),
            )

            submit_schedule = self.scheduler_client.post_schedule(schedule=schedule_request)
            messages.success(self.request, _("Your report has been scheduled."))
            return submit_schedule
        except SchedulerError as error:
            return messages.error(self.request, error.message)

    def delete_report_schedule(self, schedule_id: str) -> None:
        try:
            self.scheduler_client.delete_schedule(schedule_id)
        except SchedulerError as error:
            messages.error(self.request, error.message)

    def edit_report_schedule(self, schedule_id: str, params):
        self.scheduler_client.patch_schedule(schedule_id=schedule_id, params=params)

    def get_report_schedules(self) -> list[dict[str, Any]]:
        try:
            return self.scheduler_client.get_scheduled_reports()
        except SchedulerError as error:
            messages.error(self.request, error.message)
        return []

    def get_task_statistics(self) -> dict[Any, Any]:
        stats = {}
        try:
            stats = self.scheduler_client.get_task_stats(self.task_type)
        except SchedulerError as error:
            messages.error(self.request, error.message)
        return stats

    def get_organization_specific_tasks(self, organizations: list[str] | None = None) -> dict[str, str | list[str]]:
        if organizations:
            raise ValueError("Bound SchedulerView does not support organization argument, use UnboundSchedulerView")
        return {"column": "organisation", "operator": "==", "value": self.organization.code}

    def run_boefje(self, katalogus_boefje: Boefje, ooi: OOI | None) -> None:
        try:
            boefje_task = BoefjeTask(
                boefje=SchedulerBoefje.model_validate(katalogus_boefje.model_dump()),
                input_ooi=ooi.reference if ooi else None,
                organization=self.organization.code,
            )

            new_task = TaskPush(
                priority=1, data=boefje_task.model_dump(), scheduler_id="boefje", organisation=self.organization.code
            )

            self.schedule_task(new_task)

        except SchedulerError as error:
            messages.error(self.request, error.message)

    def run_boefje_for_oois(self, boefje: Boefje, oois: list[OOI]) -> None:
        try:
            if not oois and not boefje.consumes:
                self.run_boefje(boefje, None)

            for ooi in oois:
                if ooi.scan_profile and ooi.scan_profile.level < boefje.scan_level:
                    self.can_raise_clearance_level(ooi, boefje.scan_level)
                self.run_boefje(boefje, ooi)
        except SchedulerError as error:
            messages.error(self.request, error.message)

    def run_normalizer(self, katalogus_normalizer: Normalizer, raw_data: RawData) -> None:
        try:
            normalizer_task = NormalizerTask(
                normalizer=SchedulerNormalizer.model_validate(katalogus_normalizer.model_dump()), raw_data=raw_data
            )

            new_task = TaskPush(
                priority=1,
                data=normalizer_task.model_dump(),
                scheduler_id="normalizer",
                organisation=self.organization.code,
            )

            self.schedule_task(new_task)
        except SchedulerError as error:
            messages.error(self.request, error.message)
