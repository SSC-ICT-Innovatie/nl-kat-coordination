from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, exc, func

from scheduler import models
from scheduler.storage import DBConn
from scheduler.storage.errors import StorageError, exception_handler
from scheduler.storage.filters import FilterRequest, apply_filter
from scheduler.storage.utils import retry


class TaskStore:
    name: str = "task_store"

    def __init__(self, dbconn: DBConn) -> None:
        self.dbconn = dbconn

    @retry()
    @exception_handler
    def get_tasks(
        self,
        scheduler_id: str | None = None,
        organisation: str | None = None,
        task_type: str | None = None,
        status: str | None = None,
        min_created_at: datetime | None = None,
        max_created_at: datetime | None = None,
        filters: FilterRequest | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[models.Task], int]:
        with self.dbconn.session.begin() as session:
            query = session.query(models.TaskDB)

            if scheduler_id is not None:
                query = query.filter(models.TaskDB.scheduler_id == scheduler_id)

            if organisation is not None:
                query = query.filter(models.TaskDB.organisation == organisation)

            if task_type is not None:
                query = query.filter(models.TaskDB.type == task_type)

            if status is not None:
                query = query.filter(models.TaskDB.status == models.TaskStatus(status).name)

            if min_created_at is not None:
                query = query.filter(models.TaskDB.created_at >= min_created_at)

            if max_created_at is not None:
                query = query.filter(models.TaskDB.created_at <= max_created_at)

            if filters is not None:
                query = apply_filter(models.TaskDB, query, filters)

            try:
                count = query.count()
                tasks_orm = query.order_by(models.TaskDB.created_at.desc()).offset(offset).limit(limit).all()
            except exc.ProgrammingError as e:
                raise StorageError(f"Invalid filter: {e}") from e

            tasks = [models.Task.model_validate(task_orm) for task_orm in tasks_orm]

            return tasks, count

    @retry()
    @exception_handler
    def get_task(self, task_id: str) -> models.Task | None:
        with self.dbconn.session.begin() as session:
            task_orm = session.query(models.TaskDB).filter(models.TaskDB.id == task_id).first()
            if task_orm is None:
                return None

            task = models.Task.model_validate(task_orm)

            return task

    @retry()
    @exception_handler
    def get_tasks_by_hash(self, task_hash: str, limit: int | None = None) -> list[models.Task] | None:
        with self.dbconn.session.begin() as session:
            query = session.query(models.TaskDB).filter(models.TaskDB.hash == task_hash)

            if limit is not None:
                query = query.limit(limit)

            tasks_orm = query.order_by(models.TaskDB.created_at.desc()).all()

            if tasks_orm is None:
                return None

            tasks = [models.Task.model_validate(task_orm) for task_orm in tasks_orm]

            return tasks

    @retry()
    @exception_handler
    def get_latest_task_by_hash(self, task_hash: str) -> models.Task | None:
        with self.dbconn.session.begin() as session:
            task_orm = (
                session.query(models.TaskDB)
                .filter(models.TaskDB.hash == task_hash)
                .order_by(models.TaskDB.created_at.desc())
                .first()
            )

            if task_orm is None:
                return None

            task = models.Task.model_validate(task_orm)

            return task

    @retry()
    @exception_handler
    def create_task(self, task: models.Task) -> models.Task | None:
        with self.dbconn.session.begin() as session:
            task_orm = models.TaskDB(**task.model_dump())
            session.add(task_orm)

            created_task = models.Task.model_validate(task_orm)

            return created_task

    @retry()
    @exception_handler
    def update_task(self, task: models.Task) -> None:
        with self.dbconn.session.begin() as session:
            # NOTE: mode="json" is used specifically to convert the Enum to as_string
            # sqlalchemy does not allow raw enums to be used in update
            (session.query(models.TaskDB).filter(models.TaskDB.id == task.id).update(task.model_dump(mode="json")))

    @retry()
    @exception_handler
    def cancel_tasks(self, scheduler_id: str, task_ids: list[str]) -> None:
        with self.dbconn.session.begin() as session:
            session.query(models.TaskDB).filter(
                models.TaskDB.scheduler_id == scheduler_id, models.TaskDB.id.in_(task_ids)
            ).update({"status": models.TaskStatus.CANCELLED.name})

    @retry()
    @exception_handler
    def get_status_count_per_hour(
        self, scheduler_id: str | None = None, organisation_id: str | None = None
    ) -> dict[str, dict[str, int]] | None:
        with self.dbconn.session.begin() as session:
            query = (
                session.query(
                    func.DATE_TRUNC("hour", models.TaskDB.modified_at).label("hour"),
                    models.TaskDB.status,
                    func.count(models.TaskDB.id).label("count"),
                )
                .filter(models.TaskDB.modified_at >= datetime.now(timezone.utc) - timedelta(hours=24))
                .group_by("hour", models.TaskDB.status)
                .order_by(desc("hour"), models.TaskDB.status)
            )

            if scheduler_id is not None:
                query = query.filter(models.TaskDB.scheduler_id == scheduler_id)

            if organisation_id is not None:
                query = query.filter(models.TaskDB.organisation == organisation_id)

            results = query.all()

            # We rely on the dict insertion order
            response: dict[str, dict[str, int]] = {}
            for row in results:
                date, status, task_count = row
                response.setdefault(date.isoformat(), {k.value: 0 for k in models.TaskStatus}).update(
                    {status.value: task_count}
                )
                response[date.isoformat()].update({"total": response[date.isoformat()].get("total", 0) + task_count})

            return response

    @retry()
    @exception_handler
    def get_status_counts(
        self, scheduler_id: str | None = None, organisation_id: str | None = None
    ) -> dict[str, int] | None:
        with self.dbconn.session.begin() as session:
            query = (
                session.query(models.TaskDB.status, func.count(models.TaskDB.id).label("count"))
                .group_by(models.TaskDB.status)
                .order_by(models.TaskDB.status)
            )

            if scheduler_id is not None:
                query = query.filter(models.TaskDB.scheduler_id == scheduler_id)

            if organisation_id is not None:
                query = query.filter(models.TaskDB.organisation == organisation_id)

            results = query.all()

            response = {k.value: 0 for k in models.TaskStatus}
            for row in results:
                status, task_count = row
                response[status.value] = task_count

            return response
