import datetime
import uuid

import fastapi
import structlog
from fastapi import status

from scheduler import context, storage
from scheduler.server import schemas, utils
from scheduler.server.errors import BadRequestError, NotFoundError


class TaskAPI:
    def __init__(self, api: fastapi.FastAPI, ctx: context.AppContext) -> None:
        self.logger: structlog.BoundLogger = structlog.getLogger(__name__)
        self.api = api
        self.ctx = ctx

        self.api.add_api_route(
            path="/tasks",
            endpoint=self.list,
            methods=["GET", "POST"],
            response_model=utils.PaginatedResponse,
            status_code=status.HTTP_200_OK,
            description="List all tasks",
        )

        self.api.add_api_route(
            path="/tasks/stats",
            endpoint=self.stats,
            methods=["GET"],
            status_code=status.HTTP_200_OK,
            description="Get task status counts for all schedulers in last 24 hours",
        )

        self.api.add_api_route(
            path="/tasks/{task_id}",
            endpoint=self.get,
            methods=["GET"],
            response_model=schemas.Task,
            status_code=status.HTTP_200_OK,
            description="Get a task",
        )

        self.api.add_api_route(
            path="/tasks/{task_id}",
            endpoint=self.patch,
            methods=["PATCH"],
            response_model=schemas.Task,
            response_model_exclude_unset=True,
            status_code=status.HTTP_200_OK,
            description="Update a task",
        )

    def list(
        self,
        request: fastapi.Request,
        scheduler_id: str | None = None,
        organisation: str | None = None,
        task_type: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 10,
        min_created_at: datetime.datetime | None = None,
        max_created_at: datetime.datetime | None = None,
        filters: storage.filters.FilterRequest | None = None,
    ) -> utils.PaginatedResponse:
        if (min_created_at is not None and max_created_at is not None) and min_created_at > max_created_at:
            raise BadRequestError("min_created_at must be less than max_created_at")

        results, count = self.ctx.datastores.task_store.get_tasks(
            scheduler_id=scheduler_id,
            organisation=organisation,
            task_type=task_type,
            status=status,
            offset=offset,
            limit=limit,
            min_created_at=min_created_at,
            max_created_at=max_created_at,
            filters=filters,
        )

        return utils.paginate(request, results, count, offset, limit)

    def get(self, task_id: uuid.UUID) -> schemas.Task:
        task = self.ctx.datastores.task_store.get_task(task_id)
        if task is None:
            raise NotFoundError(f"task not found, by task_id: {task_id}")
        return task

    def patch(self, task_id: uuid.UUID, item: schemas.TaskPatch) -> schemas.Task:
        task_db = self.ctx.datastores.task_store.get_task(task_id)

        if task_db is None:
            raise NotFoundError(f"task not found, by task_id: {task_id}")

        patch_data = item.model_dump(exclude_unset=True)
        if len(patch_data) == 0:
            raise BadRequestError("no data to patch")

        # Update task
        updated_task = task_db.model_copy(update=patch_data)
        self.ctx.datastores.task_store.update_task(updated_task)

        return updated_task

    def stats(
        self, scheduler_id: str | None = None, organisation_id: str | None = None
    ) -> dict[str, dict[str, int]] | None:
        return self.ctx.datastores.task_store.get_status_count_per_hour(scheduler_id, organisation_id)
