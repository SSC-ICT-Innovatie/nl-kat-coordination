from concurrent import futures
from datetime import datetime, timezone
from typing import Any, Literal

from opentelemetry import trace

from scheduler import context, models
from scheduler.schedulers import Scheduler
from scheduler.schedulers.errors import exception_handler
from scheduler.storage import filters

tracer = trace.get_tracer(__name__)


class ReportScheduler(Scheduler):
    """Scheduler implementation for the creation of ReportTask models."""

    ID: Literal["report"] = "report"
    TYPE: models.SchedulerType = models.SchedulerType.REPORT
    ITEM_TYPE: Any = models.ReportTask

    def __init__(self, ctx: context.AppContext):
        """Initializes the NormalizerScheduler.

        Args:
            ctx (context.AppContext): Application context of shared data (e.g.
                configuration, external services connections).
        """
        super().__init__(ctx=ctx, scheduler_id=self.ID, create_schedule=True, auto_calculate_deadline=False)

    def run(self) -> None:
        """The run method is called when the schedulers is started. It will
        start the rescheduling process for the ReportTask models that are
        scheduled.
        """
        # Rescheduling
        self.run_in_thread(name="ReportScheduler-rescheduling", target=self.process_rescheduling, interval=60.0)
        self.logger.info(
            "Report scheduler started", scheduler_id=self.scheduler_id, item_type=self.queue.item_type.__name__
        )

    @tracer.start_as_current_span(name="ReportScheduler.process_rescheduling")
    def process_rescheduling(self):
        schedules, _ = self.ctx.datastores.schedule_store.get_schedules(
            filters=filters.FilterRequest(
                filters=[
                    filters.Filter(column="scheduler_id", operator="eq", value=self.scheduler_id),
                    filters.Filter(column="deadline_at", operator="lt", value=datetime.now(timezone.utc)),
                    filters.Filter(column="enabled", operator="eq", value=True),
                ]
            )
        )

        # Create report tasks for the schedules
        report_tasks = []
        for schedule in schedules:
            report_task = models.ReportTask.model_validate(schedule.data)
            report_tasks.append(report_task)

        with futures.ThreadPoolExecutor(thread_name_prefix=f"TPE-{self.scheduler_id}-rescheduling") as executor:
            for report_task in report_tasks:
                executor.submit(
                    self.push_report_task,
                    report_task,
                    report_task.organisation_id,
                    self.create_schedule,
                    self.process_rescheduling.__name__,
                )

    @exception_handler
    @tracer.start_as_current_span("ReportScheduler.push_report_task")
    def push_report_task(
        self, report_task: models.ReportTask, organisation_id: str, create_schedule: bool, caller: str = ""
    ) -> None:
        task = models.Task(
            scheduler_id=self.scheduler_id,
            organisation=organisation_id,
            priority=int(datetime.now().timestamp()),
            type=self.ITEM_TYPE.type,
            hash=report_task.hash,
            data=report_task.model_dump(),
        )

        self.push_item_to_queue_with_timeout(task, self.max_tries)

        self.logger.info(
            "Created report task",
            task_id=task.id,
            task_hash=task.hash,
            scheduler_id=self.scheduler_id,
            organisation_id=organisation_id,
            caller=caller,
        )
