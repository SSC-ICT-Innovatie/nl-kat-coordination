import datetime
import uuid
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# A deliberate relative import to make this module self-contained
from .job_models import BoefjeMeta, NormalizerMeta


class JobRuntimeError(RuntimeError):
    """Base exception class for exceptions raised during running of jobs"""


class Queue(BaseModel):
    id: str
    size: int


class TaskStatus(Enum):
    """Status of a task."""

    PENDING = "pending"
    QUEUED = "queued"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    id: uuid.UUID
    scheduler_id: str
    schedule_id: str | None
    organisation: str
    priority: int
    status: TaskStatus
    type: str
    hash: str | None = None
    data: BoefjeMeta | NormalizerMeta
    created_at: datetime.datetime
    modified_at: datetime.datetime


class TaskPop(BaseModel):
    results: list[Task]


class StatusEnum(str, Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class File(BaseModel):
    name: str
    content: str = Field(json_schema_extra={"contentEncoding": "base64"})
    tags: set[str] | None = None


class BoefjeInput(BaseModel):
    output_url: str
    task: Task
    model_config = ConfigDict(extra="forbid")


class BoefjeOutput(BaseModel):
    status: StatusEnum
    files: list[File] | None = None


class WorkerManager:
    class Queue(Enum):
        BOEFJES = "boefje"
        NORMALIZERS = "normalizer"

    def run(self, queue: Queue) -> None:
        raise NotImplementedError()


class BoefjeHandler:
    def handle(self, task: Task) -> tuple[BoefjeMeta, BoefjeOutput] | None | Literal[False]:
        """
        With regard to the return type:
            :rtype: tuple[BoefjeMeta, list[tuple[set, bytes | str]]] | None | bool

        The return type signals the app how the boefje was handled. A successful run returns a tuple of the updated
        boefje_meta and its results to allow for deduplication. A failure returns None. And for now as a temporary
        solution, we return False if the task was not handled here directly, but delegated to the Docker runner.
        """
        raise NotImplementedError()

    def copy_raw_files(
        self, task: Task, output: tuple[BoefjeMeta, BoefjeOutput] | Literal[False], duplicated_tasks: list[Task]
    ) -> None:
        raise NotImplementedError()


class NormalizerHandler:
    def handle(self, task: Task) -> None:
        raise NotImplementedError()


class PaginatedTasksResponse(BaseModel):
    count: int
    next: str | None = None
    previous: str | None = None
    results: list[Task]


class SchedulerClientInterface:
    def pop_items(
        self, queue: WorkerManager.Queue, filters: dict[str, list[dict[str, Any]]] | None = None, limit: int = 1
    ) -> list[Task]:
        raise NotImplementedError()

    def patch_task(self, task_id: uuid.UUID, status: TaskStatus) -> None:
        raise NotImplementedError()

    def get_task(self, task_id: uuid.UUID, hydrate: bool = True) -> Task:
        raise NotImplementedError()

    def push_item(self, p_item: Task) -> None:
        raise NotImplementedError()


class BoefjeStorageInterface:
    def save_output(self, boefje_meta: BoefjeMeta, boefje_output: BoefjeOutput) -> dict[str, uuid.UUID]:
        raise NotImplementedError()
