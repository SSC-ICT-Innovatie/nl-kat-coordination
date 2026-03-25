import uuid
from datetime import datetime
from typing import Any

import structlog
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
from tools.forms.scheduler import TaskFilterForm

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


class SchedulerView(OctopoesView):
    task_type: str

    task_filter_form = TaskFilterForm

    report_schedule_form_start_date_choice = ReportScheduleStartDateChoiceForm  # today or different date
    report_schedule_form_start_date_time_recurrence = ReportScheduleStartDateForm  # date, time and recurrence

    report_schedule_form_recurrence_choice = ReportRecurrenceChoiceForm  # once or repeat

    report_name_form = ReportNameForm  # name format

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.scheduler_client = scheduler_client(self.organization.code)
        if hasattr(self, "task_type"):
            self.scheduler_id = self.task_type

    def get_task_filters(self) -> dict[str, Any]:
        return {
            "scheduler_id": self.scheduler_id,
            "task_type": self.task_type,
            "plugin_id": None,  # plugin_id present and set at plugin detail
            **self.get_task_filter_form_data(),
        } | self.get_organization_specific_tasks()

    def get_organization_specific_tasks(self) -> dict[str, dict[str, list[dict[str, str]]]]:
        if self.organization.code:
            return {
                "filters": {"filters": [{"column": "organisation", "operator": "==", "value": self.organization.code}]}
            }
        return {}

    def get_task_filter_form_data(self) -> dict[str, Any]:
        form_data = self.get_task_filter_form().data.dict()
        return {k: v for k, v in form_data.items() if v}

    def count_active_task_filters(self):
        form_data = self.get_task_filter_form_data()

        count = len(form_data)
        for task_filter in form_data:
            if task_filter in ("observed_at", "ooi_id"):
                count -= 1

        return count

    def get_task_filter_form(self) -> TaskFilterForm:
        return self.task_filter_form(self.request.GET)

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
            if task.organization_id() != self.organization.code:
                raise SchedulerTaskNotFound()

            return task
        except SchedulerTaskNotFound:
            raise Http404()

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
            return messages.error(self.request, error.message)

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

    def get_output_oois(self, task):
        try:
            return self.octopoes_api_connector.list_origins(
                valid_time=task.data.raw_data.boefje_meta.ended_at, task_id=task.id
            )[0].result
        except IndexError:
            return []
        except SchedulerError as error:
            messages.error(self.request, error.message)
            return []

    def get_json_task_details(self) -> JsonResponse:
        try:
            task = self.get_task_details(self.kwargs["task_id"])
            if task:
                return JsonResponse(
                    {
                        "oois": self.get_output_oois(task),
                        "valid_time": task.data.raw_data.boefje_meta.ended_at.strftime("%Y-%m-%dT%H:%M:%S"),
                    },
                    safe=False,
                )
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
            else:
                return None
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
                if task.organization_id() != self.organization.code:
                    raise SchedulerTaskNotFound()

                new_id = uuid.uuid4()
                task.data.id = new_id

                new_task = TaskPush(
                    id=new_id,
                    scheduler_id=task.scheduler_id,
                    organisation=self.organization.code,
                    priority=1,
                    data=task.data.model_dump(),
                )

                self.schedule_task(new_task)
            else:
                raise SchedulerTaskNotFound()
        except SchedulerTaskNotFound:
            raise Http404()

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
            logger.info(
                "Normalizer Task created manually",
                event_code="800051",
                boefje=katalogus_normalizer.id,
                task_id=new_task.id,
            )
        except SchedulerError as error:
            messages.error(self.request, error.message)

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
            logger.info(
                "Boefje Task created manually", event_code="800051", boefje=katalogus_boefje.id, task_id=new_task.id
            )
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
