from __future__ import annotations

import collections
import datetime
import uuid
from enum import Enum
from functools import cached_property
from typing import Any

import httpx
import structlog
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from httpx import ConnectError, HTTPError, HTTPStatusError, RequestError, codes
from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny, TypeAdapter, ValidationError

from rocky.health import ServiceHealth

logger = structlog.get_logger(__name__)


class Boefje(BaseModel):
    """Boefje representation."""

    id: str
    name: str | None = Field(default=None)
    version: str | None = Field(default=None)
    oci_image: str | None = Field(default=None)


class BoefjeMeta(BaseModel):
    """BoefjeMeta is the response object returned by the Bytes API"""

    id: uuid.UUID
    boefje: Boefje
    input_ooi: str | None = None
    arguments: dict[str, Any]
    organization: str
    started_at: datetime.datetime | None = None
    ended_at: datetime.datetime | None = None


class RawData(BaseModel):
    id: uuid.UUID
    boefje_meta: BoefjeMeta
    mime_types: list[dict[str, str]]
    secure_hash: str | None = None
    hash_retrieval_link: str | None = None


class Normalizer(BaseModel):
    """Normalizer representation."""

    id: str | None = None
    name: str | None = None
    version: str | None = Field(default=None)


class NormalizerMeta(BaseModel):
    id: uuid.UUID
    raw_data: RawData
    normalizer: Normalizer
    started_at: datetime.datetime
    ended_at: datetime.datetime


class NormalizerTask(BaseModel):
    """NormalizerTask represent data needed for a Normalizer to run."""

    type: str = "normalizer"

    id: uuid.UUID | None = None
    normalizer: Normalizer
    raw_data: RawData


class BoefjeTask(BaseModel):
    """BoefjeTask represent data needed for a Boefje to run."""

    type: str = "boefje"

    id: uuid.UUID | None = None
    boefje: Boefje
    input_ooi: str | None = None
    organization: str
    deduplication_key: uuid.UUID | None = None


class ReportTask(BaseModel):
    """ReportTask represent data needed for a Report to run."""

    type: str = "report"

    organisation_id: str
    report_recipe_id: str


class TaskStatus(Enum):
    # Task has been created but not yet queued
    PENDING = "pending"

    # Task has been pushed onto queue and is ready to be picked up
    QUEUED = "queued"

    # Task has been picked up by a worker
    DISPATCHED = "dispatched"

    # Task has been picked up by a worker, and the worker indicates that it is
    # running.
    RUNNING = "running"

    # Task has been completed
    COMPLETED = "completed"

    # Task has failed
    FAILED = "failed"

    # Task has been cancelled
    CANCELLED = "cancelled"


class Task(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    scheduler_id: str
    schedule_id: str | None = None
    organisation: str
    priority: int
    status: TaskStatus | None = TaskStatus.PENDING
    type: str | None = None
    hash: str | None = None
    data: SerializeAsAny[BoefjeTask | NormalizerTask | ReportTask]
    created_at: datetime.datetime | None = None
    modified_at: datetime.datetime | None = None

    def organization_id(self) -> str:
        if isinstance(self.data, BoefjeTask):
            return self.data.organization

        if isinstance(self.data, NormalizerTask):
            return self.data.raw_data.boefje_meta.organization

        if isinstance(self.data, ReportTask):
            return self.data.organisation_id

        raise ValueError("No organization found related to task")


class TaskPush(BaseModel):
    id: uuid.UUID | None = None
    scheduler_id: str | None = None
    organisation: str
    priority: int | None = None
    data: dict


class ScheduleRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scheduler_id: str
    organisation: str
    data: dict
    schedule: str | None = None
    deadline_at: str


class ScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scheduler_id: str
    organisation: str
    hash: str
    data: dict
    enabled: bool
    schedule: str | None
    deadline_at: datetime.datetime | None
    created_at: datetime.datetime
    modified_at: datetime.datetime


class SchedulerResponse(BaseModel):
    id: str
    enabled: bool
    priority_queue: dict[str, Any]
    last_activity: str | None


class SchedulerNoResponse(BaseModel):
    detail: str


class Queue(BaseModel):
    id: str
    size: int


class PaginatedTasksResponse(BaseModel):
    count: int
    next: str | None = None
    previous: str | None = None
    results: list[Task]


class TaskPop(BaseModel):
    results: list[Task]


class PaginatedSchedulesResponse(BaseModel):
    count: int
    next: str | None = None
    previous: str | None = None
    results: list[ScheduleResponse]


class LazyTaskList:
    HARD_LIMIT = 500

    def __init__(self, scheduler_client: SchedulerClient, **kwargs: Any):
        self.scheduler_client = scheduler_client
        self.kwargs = kwargs
        self._count: int | None = None

    @cached_property
    def count(self) -> int:
        if self._count is None:
            self._count = self.scheduler_client.list_tasks(limit=0, **self.kwargs).count
        return self._count

    def __len__(self):
        return self.count

    def __getitem__(self, key: slice | int) -> list[Task]:
        if isinstance(key, slice):
            offset = key.start or 0
            limit = min(LazyTaskList.HARD_LIMIT, key.stop - offset or key.stop or LazyTaskList.HARD_LIMIT)

        elif isinstance(key, int):
            offset = key
            limit = 1
        else:
            raise TypeError("Invalid slice argument type.")

        logger.debug("Getting max %s lazy items at offset %s with filter %s", limit, offset, self.kwargs)
        res = self.scheduler_client.list_tasks(limit=limit, offset=offset, **self.kwargs)

        self._count = res.count

        return res.results


class SchedulerError(Exception):
    message: str = _("The Scheduler has an unexpected error. Check the Scheduler logs for further details.")

    def __init__(self, *args: object, extra_message: str | None = None) -> None:
        super().__init__(*args)
        if extra_message is not None:
            self.message = extra_message + self.message

    def __str__(self) -> str:
        return str(self.message)


class SchedulerConnectError(SchedulerError):
    message = _("Could not connect to Scheduler. Service is possibly down.")


class SchedulerValidationError(SchedulerError):
    message = _("Your request could not be validated.")


class SchedulerTaskNotFound(SchedulerError):
    message = _("Task could not be found.")


class SchedulerTooManyRequestError(SchedulerError):
    message = _("Scheduler is receiving too many requests. Increase SCHEDULER_PQ_MAXSIZE or wait for task to finish.")


class SchedulerBadRequestError(SchedulerError):
    message = _("Bad request. Your request could not be interpreted by the Scheduler.")


class SchedulerConflictError(SchedulerError):
    message = _("The Scheduler has received a conflict. Your task is already in queue.")


class SchedulerHTTPError(SchedulerError):
    message = _("A HTTPError occurred. See Scheduler logs for more info.")


class SchedulerClient:
    def __init__(self, base_uri: str, organization_code: str | None):
        self._client = httpx.Client(base_url=base_uri, timeout=settings.ROCKY_OUTGOING_REQUEST_TIMEOUT)
        self.organization_code = organization_code

    def list_schedules(self, **kwargs) -> PaginatedSchedulesResponse:
        try:
            kwargs = {k: v for k, v in kwargs.items() if v is not None}  # filter Nones from kwargs
            res = self._client.get("/schedules", params=kwargs)
            res.raise_for_status()
            return PaginatedSchedulesResponse.model_validate_json(res.content)
        except ValidationError:
            raise SchedulerValidationError(extra_message=_("Schedule list: "))
        except ConnectError:
            raise SchedulerConnectError(extra_message=_("Schedule list: "))

    def get_schedule_details(self, schedule_id: str) -> ScheduleResponse:
        try:
            res = self._client.get(f"/schedules/{schedule_id}")
            res.raise_for_status()
            return ScheduleResponse.model_validate_json(res.content)
        except ConnectError:
            raise SchedulerConnectError()

    def post_schedule_search(self, filters: dict[str, list[dict[str, Any]]]) -> PaginatedSchedulesResponse:
        try:
            filters["filters"].append({"column": "organisation", "operator": "eq", "value": self.organization_code})
            res = self._client.post("/schedules/search", json=filters)
            res.raise_for_status()
            return PaginatedSchedulesResponse.model_validate_json(res.content)
        except ConnectError:
            raise SchedulerConnectError()

    def patch_schedule(self, schedule_id: str, params: dict[str, Any]) -> None:
        try:
            response = self._client.patch(f"/schedules/{schedule_id}", json=params)
            response.raise_for_status()
            logger.info("Schedule updated", event_code=800082, schedule_id=schedule_id, params=params)
        except (HTTPStatusError, ConnectError):
            raise SchedulerHTTPError()

    def post_schedule(self, schedule: ScheduleRequest) -> ScheduleResponse:
        try:
            res = self._client.post("/schedules", json=schedule.model_dump(exclude_none=True))
            logger.info(res.content)
            res.raise_for_status()
            logger.info("Schedule created", event_code=800081, schedule=schedule)

            return ScheduleResponse.model_validate_json(res.content)
        except ValidationError:
            raise SchedulerValidationError(extra_message="Report schedule failed: ")
        except HTTPStatusError:
            raise SchedulerHTTPError()
        except ConnectError:
            raise SchedulerConnectError()

    def delete_schedule(self, schedule_id: str) -> None:
        try:
            response = self._client.delete(f"/schedules/{schedule_id}")
            response.raise_for_status()
            logger.info("Schedule deleted", event_code=800083, schedule_id=schedule_id)
        except (HTTPStatusError, ConnectError):
            raise SchedulerHTTPError()

    def list_tasks(self, **kwargs) -> PaginatedTasksResponse:
        try:
            filter_key = "filters"
            params = {k: v for k, v in kwargs.items() if v is not None if k != filter_key}  # filter Nones from kwargs
            endpoint = "/tasks"
            res = self._client.post(endpoint, params=params, json=kwargs.get(filter_key))
            return PaginatedTasksResponse.model_validate_json(res.content)
        except ValidationError:
            raise SchedulerValidationError(extra_message=_("Task list: "))
        except ConnectError:
            raise SchedulerConnectError(extra_message=_("Task list: "))

    def get_task_details(self, task_id: str) -> Task:
        try:
            task_id = str(uuid.UUID(task_id))
            return Task.model_validate_json(self._get(f"/tasks/{task_id}", "content"))
        except ValueError:
            raise SchedulerTaskNotFound()

    def push_task(self, item: Task) -> None:
        try:
            res = self._client.post(
                f"/schedulers/{item.scheduler_id}/push",
                content=item.model_dump_json(exclude_none=True),
                headers={"Content-Type": "application/json"},
            )
            res.raise_for_status()
        except HTTPStatusError as http_error:
            code = http_error.response.status_code
            if code == codes.TOO_MANY_REQUESTS:
                raise SchedulerTooManyRequestError() from http_error
            elif code == codes.BAD_REQUEST:
                raise SchedulerBadRequestError() from http_error
            elif code == codes.CONFLICT:
                raise SchedulerConflictError() from http_error
        except RequestError as request_error:
            raise SchedulerError() from request_error

    def get_queues(self) -> list[Queue]:
        response = self._client.get("/queues")
        response.raise_for_status()

        return TypeAdapter(list[Queue]).validate_json(response.content)

    def pop_item(self, scheduler_id: str) -> Task | None:
        response = self._client.post(f"/schedulers/{scheduler_id}/pop?limit=1")
        response.raise_for_status()

        popped_items = TypeAdapter(TaskPop | None).validate_json(response.content)
        if len(popped_items.results) == 0:
            return None

        return popped_items.results[0]

    def pop_items(self, scheduler_id: str, filters: dict[str, Any]) -> TaskPop | None:
        response = self._client.post(f"/schedulers/{scheduler_id}/pop", json=filters)

        return TypeAdapter(TaskPop | None).validate_json(response.content)

    def patch_task(self, task_id: uuid.UUID, status: TaskStatus) -> None:
        response = self._client.patch(f"/tasks/{task_id}", json={"status": status.value})
        response.raise_for_status()

    def health(self) -> ServiceHealth:
        return ServiceHealth.model_validate_json(self._get("/health", return_type="content"))

    def _get_task_stats(self, scheduler_id: str, organisation_id: str | None = None) -> dict:
        """Return task stats for specific scheduler."""
        if organisation_id is None:
            return self._get(f"/tasks/stats?scheduler_id={scheduler_id}")  # type: ignore

        return self._get(f"/tasks/stats?scheduler_id={scheduler_id}&organisation_id={organisation_id}")  # type: ignore

    def get_task_stats(self, task_type: str) -> dict:
        """Return task stats for specific task type."""
        return self._get_task_stats(scheduler_id=task_type, organisation_id=self.organization_code)

    @staticmethod
    def _merge_stat_dicts(dicts: list[dict]) -> dict:
        """Merge multiple stats dicts."""
        stat_sum: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        for dct in dicts:
            for timeslot, counts in dct.items():
                stat_sum[timeslot].update(counts)
        return dict(stat_sum)

    def get_task_stats_for_all_organizations(self, scheduler_id: str) -> dict:
        return self._get_task_stats(scheduler_id)

    def get_combined_schedulers_stats(self, scheduler_id: str, organization_codes: list[str]) -> dict:
        """Return merged stats for a set of scheduler ids."""
        return self._merge_stat_dicts(
            dicts=[self._get_task_stats(scheduler_id, org_code) for org_code in organization_codes]
        )

    def _get(self, path: str, return_type: str = "json") -> dict | bytes:
        """Helper to do a get request and raise warning for path."""
        try:
            res = self._client.get(path)
            res.raise_for_status()
        except HTTPError as exc:
            raise SchedulerError(path) from exc
        except ConnectError as exc:
            raise SchedulerConnectError(path) from exc

        if return_type == "content":
            return res.content
        return res.json()

    def get_scheduled_reports(self) -> list[dict[str, Any]]:
        try:
            filters: dict[str, list[dict[str, Any]]] = {
                "filters": [
                    {"column": "scheduler_id", "operator": "eq", "value": "report"},
                    {"column": "organisation", "operator": "eq", "value": self.organization_code},
                ]
            }

            response = self._client.post("/schedules/search", json=filters)
            response.raise_for_status()
        except HTTPStatusError:
            logger.error("A HTTPStatusError occurred. Check logs for more info.")
        return response.json()["results"]


def scheduler_client(organization_code: str | None) -> SchedulerClient:
    return SchedulerClient(settings.SCHEDULER_API, organization_code)
