import uuid
from concurrent import futures
from typing import Any, Literal

from opentelemetry import trace
from pydantic import ValidationError
from typing_extensions import override

from scheduler import clients, context, models
from scheduler.schedulers import Scheduler, rankers
from scheduler.schedulers.errors import exception_handler

tracer = trace.get_tracer(__name__)


class NormalizerScheduler(Scheduler):
    """Scheduler implementation for the creation of NormalizerTask models.

    Attributes:
        ranker: The ranker to calculate the priority of a task.
    """

    ID: Literal["normalizer"] = "normalizer"
    TYPE: models.SchedulerType = models.SchedulerType.NORMALIZER
    ITEM_TYPE: Any = models.NormalizerTask

    def __init__(self, ctx: context.AppContext):
        """Initializes the NormalizerScheduler.

        Args:
            ctx (context.AppContext): Application context of shared data (e.g.
                configuration, external services connections).
        """
        super().__init__(ctx=ctx, scheduler_id=self.ID, create_schedule=False, auto_calculate_deadline=False)
        self.ranker = rankers.NormalizerRanker(ctx=self.ctx)

    def run(self) -> None:
        """The run method is called when the scheduler is started. It will
        start the listeners and the scheduling loops in separate threads. It
        is mainly tasked with populating the queue with tasks.

        * Raw data listener: This listener will listen to the raw file received
        messaging queue. When a new raw file is received, it will create a task
        for each normalizer that is registered for the mime type of the raw
        file.
        """
        self.listeners["raw_data"] = clients.RawData(
            dsn=str(self.ctx.config.host_raw_data),
            queue="raw_file_received",
            func=self.process_raw_data,
            prefetch_count=self.ctx.config.rabbitmq_prefetch_count,
        )

        self.run_in_thread(name="NormalizerScheduler-raw_file", target=self.listeners["raw_data"].listen, loop=False)

        self.logger.info(
            "Normalizer scheduler started", scheduler_id=self.scheduler_id, item_type=self.queue.item_type.__name__
        )

    @tracer.start_as_current_span("NormalizerScheduler.process_raw_data")
    def process_raw_data(self, body: bytes) -> None:
        """Create tasks for the received raw data.

        Args:
            latest_raw_data: A `RawData` object that was received from the
            message queue.
        """
        try:
            # Convert body into a RawDataReceivedEvent
            latest_raw_data = models.RawDataReceivedEvent.model_validate_json(body)
            self.logger.debug(
                "Received raw data %s",
                latest_raw_data.raw_data.id,
                raw_data_id=latest_raw_data.raw_data.id,
                scheduler_id=self.scheduler_id,
            )
        except ValidationError:
            self.logger.exception("Failed to validate raw data", scheduler_id=self.scheduler_id)
            return

        # Check if the raw data doesn't contain an error mime-type,
        # we don't need to create normalizers when the raw data returned
        # an error.
        if self.has_raw_data_errors(latest_raw_data.raw_data):
            self.logger.debug(
                "Skipping raw data %s with error mime type",
                latest_raw_data.raw_data.id,
                raw_data_id=latest_raw_data.raw_data.id,
            )
            return

        # Get all unique normalizers for the mime types of the raw data
        normalizers: dict[str, models.Plugin] = {}
        for mime_type in latest_raw_data.raw_data.mime_types:
            normalizers_by_mime_type = self.ctx.services.katalogus.get_normalizers_by_org_id_and_type(
                latest_raw_data.organization, mime_type.get("value")
            )

            self.logger.debug(
                "Found normalizers for mime type",
                mime_type=mime_type.get("value"),
                normalizers=normalizers_by_mime_type,
            )

            for normalizer in normalizers_by_mime_type:
                normalizers[normalizer.id] = normalizer

        unique_normalizers = list(normalizers.values())

        self.logger.debug(
            "Found normalizers for raw data",
            raw_data_id=latest_raw_data.raw_data.id,
            mime_types=[mime_type.get("value") for mime_type in latest_raw_data.raw_data.mime_types],
            normalizers=[normalizer.id for normalizer in unique_normalizers],
            scheduler_id=self.scheduler_id,
        )

        # Create tasks for the normalizers
        normalizer_tasks = []
        for normalizer in unique_normalizers:
            if not self.has_normalizer_permission_to_run(normalizer):
                self.logger.debug(
                    "Normalizer is not allowed to run: %s",
                    normalizer.id,
                    normalizer_id=normalizer.id,
                    scheduler_id=self.scheduler_id,
                )
                continue

            normalizer_task = models.NormalizerTask(
                normalizer=models.Normalizer.model_validate(normalizer.model_dump()), raw_data=latest_raw_data.raw_data
            )

            normalizer_tasks.append(normalizer_task)

        with futures.ThreadPoolExecutor(thread_name_prefix=f"TPE-{self.scheduler_id}-raw_data") as executor:
            for normalizer_task in normalizer_tasks:
                executor.submit(
                    self.push_normalizer_task, normalizer_task, latest_raw_data.organization, self.create_schedule
                )

    @exception_handler
    @tracer.start_as_current_span("NormalizerScheduler.push_normalizer_task")
    def push_normalizer_task(
        self, normalizer_task: models.NormalizerTask, organisation_id: str, create_schedule: bool, caller: str = ""
    ) -> None:
        is_running = self.has_normalizer_task_started_running(normalizer_task)
        if is_running:
            self.logger.debug(
                "Task is still running: %s",
                normalizer_task.id,
                task_id=normalizer_task.id,
                scheduler_id=self.scheduler_id,
                caller=caller,
            )
            return

        task = models.Task(
            id=normalizer_task.id,
            scheduler_id=self.scheduler_id,
            organisation=organisation_id,
            type=normalizer_task.type,
            hash=normalizer_task.hash,
            data=normalizer_task.model_dump(),
        )

        task.priority = self.ranker.rank(normalizer_task)
        self.push_item_to_queue_with_timeout(task, self.max_tries, create_schedule=create_schedule)

        self.logger.info(
            "Created normalizer task",
            task_id=task.id,
            task_hash=task.hash,
            normalizer_id=normalizer_task.normalizer.id,
            raw_data_id=normalizer_task.raw_data.id,
            scheduler_id=self.scheduler_id,
            organisation_id=organisation_id,
            caller=caller,
        )

    @override
    def push_item_to_queue(self, item: models.Task, create_schedule: bool = True) -> models.Task:
        """Some normalizer scheduler specific logic before pushing the item to the
        queue.

        The task.id and the normalizer_task.id should be the same, this assumption
        is made by the task runner. Here we enforce this by setting the
        boefje_task.id to the task.id if they are not the same.
        """
        normalizer_task = models.NormalizerTask.model_validate(item.data)

        # Check if id's are unique and correctly set. Same id's are necessary
        # for the task runner.
        if item.id != normalizer_task.id:
            new_id = uuid.uuid4()

            normalizer_task.id = new_id
            item.id = new_id
            item.data = normalizer_task.model_dump()

        return super().push_item_to_queue(item=item, create_schedule=create_schedule)

    def has_normalizer_permission_to_run(self, normalizer: models.Plugin) -> bool:
        """Check if the task is allowed to run.

        Args:
            normalizer: The normalizer to check.

        Returns:
            True if the task is allowed to run, False otherwise.
        """
        if not normalizer.enabled:
            self.logger.debug(
                "Normalizer: %s is disabled", normalizer.id, normalizer_id=normalizer.id, scheduler_id=self.scheduler_id
            )
            return False

        return True

    def has_normalizer_task_started_running(
        self, task: models.NormalizerTask, task_db: models.Task | None = None
    ) -> bool:
        """Check if the same task is already running.

        Args:
            task: The NormalizerTask to check.

        Returns:
            True if the task is still running, False otherwise.
        """
        # Is task still running according to the datastore?
        if task_db is not None and task_db.status not in [models.TaskStatus.COMPLETED, models.TaskStatus.FAILED]:
            self.logger.debug(
                "Task is still running, according to the datastore",
                task_id=task_db.id,
                task_hash=task.hash,
                scheduler_id=self.scheduler_id,
            )
            return True

        return False

    def has_raw_data_errors(self, raw_data: models.RawData) -> bool:
        """Check if the raw data contains errors.

        Args:
            raw_data: The raw data to check.

        Returns:
            True if the raw data contains errors, False otherwise.
        """
        return any(mime_type.get("value", "").startswith("error/") for mime_type in raw_data.mime_types)
