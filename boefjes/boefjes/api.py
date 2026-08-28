import multiprocessing
import uuid
from datetime import datetime, timezone
from multiprocessing.context import ForkContext, ForkProcess
from typing import Any
from uuid import UUID

import structlog
from fastapi import Body, Depends, FastAPI, HTTPException
from httpx import HTTPError, HTTPStatusError
from pydantic import BaseModel
from uvicorn import Config, Server

from boefjes.clients.bytes_client import BytesAPIClient
from boefjes.clients.scheduler_client import SchedulerAPIClient
from boefjes.config import settings
from boefjes.dependencies.plugins import get_plugin_service
from boefjes.worker.interfaces import BoefjeInput, BoefjeOutput, StatusEnum, Task, TaskStatus, WorkerManager
from boefjes.worker.repository import _default_mime_types

app = FastAPI(title="Boefje API")
logger = structlog.get_logger(__name__)
ctx: ForkContext = multiprocessing.get_context("fork")


class UvicornServer(ForkProcess):
    def __init__(self, config: Config):
        super().__init__()
        self.server = Server(config=config)
        self.config = config

    def stop(self) -> None:
        self.terminate()

    def run(self, *args, **kwargs):
        self.server.run()


def run():
    config = Config(app, host=settings.api_host, port=settings.api_port)
    instance = UvicornServer(config=config)
    instance.start()
    return instance


# Model for partial updates, only allowing a status update
class TaskIn(BaseModel):
    status: TaskStatus


def get_scheduler_client(plugin_service=Depends(get_plugin_service)):
    return SchedulerAPIClient(plugin_service, str(settings.scheduler_api))


def get_bytes_client():
    return BytesAPIClient(str(settings.bytes_api), username=settings.bytes_username, password=settings.bytes_password)


@app.get("/healthz")
async def root():
    return "OK"


@app.get("/api/v0/tasks/{task_id}", response_model=BoefjeInput)
def boefje_input(task_id: UUID, scheduler_client: SchedulerAPIClient = Depends(get_scheduler_client)) -> BoefjeInput:
    task = get_task_from_scheduler(task_id, scheduler_client)

    if task.status is not TaskStatus.RUNNING:
        raise HTTPException(status_code=403, detail="Task does not have status running")

    output_url = str(settings.api).rstrip("/") + f"/api/v0/tasks/{task_id}"
    return BoefjeInput(task=task, output_url=output_url)


@app.post("/api/v0/tasks/{task_id}")
def boefje_output(
    task_id: UUID,
    boefje_output: BoefjeOutput,
    scheduler_client: SchedulerAPIClient = Depends(get_scheduler_client),
    bytes_client: BytesAPIClient = Depends(get_bytes_client),
) -> dict[str, uuid.UUID]:
    task = get_task_from_scheduler(task_id, scheduler_client)
    boefje_meta = task.data

    if task.status is not TaskStatus.RUNNING:
        raise HTTPException(status_code=403, detail="Task does not have status running")

    boefje_meta.started_at = task.modified_at
    boefje_meta.ended_at = datetime.now(timezone.utc)

    try:
        bytes_client.login()
        bytes_client.save_boefje_meta(boefje_meta)

        bytes_response = {}

        if boefje_output.files:
            mime_types = _default_mime_types(boefje_meta.boefje)
            for file in boefje_output.files:
                file.tags = set(mime_types.union(file.tags)) if file.tags else set(mime_types)

            # when supported, also save file.name to Bytes
            bytes_response = bytes_client.save_raws(task_id, boefje_output)
    except HTTPError:
        scheduler_client.patch_task(task_id, TaskStatus.FAILED)
        return {}

    if boefje_output.status == StatusEnum.COMPLETED:
        scheduler_client.patch_task(task_id, TaskStatus.COMPLETED)
    elif boefje_output.status == StatusEnum.FAILED:
        scheduler_client.patch_task(task_id, TaskStatus.FAILED)

    return bytes_response


def get_task_from_scheduler(task_id: UUID, scheduler_client: SchedulerAPIClient):
    try:
        task = scheduler_client.get_task(task_id)
    except HTTPError as e:
        if isinstance(e, HTTPStatusError) and e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Task not found")
        else:
            logger.exception("Failed to get task from scheduler")
            raise HTTPException(status_code=500, detail="Internal server error")
    return task


# The "scheduler proxy" endpoints


@app.post("/api/v0/scheduler/{queue_id}/pop", response_model=list[Task], tags=["scheduler"])
def pop_tasks(
    queue_id: str,
    limit: int = 1,
    filters: dict[str, Any] | None = Body(...),
    scheduler_client: SchedulerAPIClient = Depends(get_scheduler_client),
) -> list[Task]:
    return scheduler_client.pop_items(WorkerManager.Queue(queue_id), filters, limit)


@app.post("/api/v0/scheduler/{queue_id}/push", tags=["scheduler"])
def push_item(
    queue_id: str, p_item: Task, scheduler_client: SchedulerAPIClient = Depends(get_scheduler_client)
) -> None:
    return scheduler_client.push_item(p_item)


@app.patch("/api/v0/scheduler/tasks/{task_id}", tags=["scheduler"])
def patch_task(
    task_id: uuid.UUID, task: TaskIn, scheduler_client: SchedulerAPIClient = Depends(get_scheduler_client)
) -> None:
    return scheduler_client.patch_task(task_id, task.status)


@app.get("/api/v0/scheduler/tasks/{task_id}", response_model=Task, tags=["scheduler"])
def get_task(task_id: uuid.UUID, scheduler_client: SchedulerAPIClient = Depends(get_scheduler_client)) -> Task:
    return get_task_from_scheduler(task_id, scheduler_client)
