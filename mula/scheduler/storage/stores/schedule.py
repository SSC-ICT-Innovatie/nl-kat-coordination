from datetime import datetime

from sqlalchemy import exc

from scheduler import models
from scheduler.storage import DBConn
from scheduler.storage.errors import StorageError, exception_handler
from scheduler.storage.filters import FilterRequest, apply_filter
from scheduler.storage.utils import retry


class ScheduleStore:
    name: str = "schedule_store"

    def __init__(self, dbconn: DBConn) -> None:
        self.dbconn = dbconn

    @retry()
    @exception_handler
    def get_schedules(
        self,
        scheduler_id: str | None = None,
        organisation: str | None = None,
        schedule_hash: str | None = None,
        enabled: bool | None = None,
        min_deadline_at: datetime | None = None,
        max_deadline_at: datetime | None = None,
        min_created_at: datetime | None = None,
        max_created_at: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
        filters: FilterRequest | None = None,
    ) -> tuple[list[models.Schedule], int]:
        with self.dbconn.session.begin() as session:
            query = session.query(models.ScheduleDB)

            if scheduler_id is not None:
                query = query.filter(models.ScheduleDB.scheduler_id == scheduler_id)

            if organisation is not None:
                query = query.filter(models.ScheduleDB.organisation == organisation)

            if enabled is not None:
                query = query.filter(models.ScheduleDB.enabled == enabled)

            if schedule_hash is not None:
                query = query.filter(models.ScheduleDB.hash == schedule_hash)

            if min_deadline_at is not None:
                query = query.filter(models.ScheduleDB.deadline_at >= min_deadline_at)

            if max_deadline_at is not None:
                query = query.filter(models.ScheduleDB.deadline_at <= max_deadline_at)

            if min_created_at is not None:
                query = query.filter(models.ScheduleDB.created_at >= min_created_at)

            if max_created_at is not None:
                query = query.filter(models.ScheduleDB.created_at <= max_created_at)

            if filters is not None:
                query = apply_filter(models.ScheduleDB, query, filters)

            try:
                count = query.count()
                schedules_orm = query.order_by(models.ScheduleDB.created_at.desc()).offset(offset).limit(limit).all()
            except exc.ProgrammingError as e:
                raise StorageError(f"Invalid filter: {e}") from e

            schedules = [models.Schedule.model_validate(schedule_orm) for schedule_orm in schedules_orm]

            return schedules, count

    @retry()
    @exception_handler
    def get_schedule(self, schedule_id: str) -> models.Schedule | None:
        with self.dbconn.session.begin() as session:
            schedule_orm = session.query(models.ScheduleDB).filter(models.ScheduleDB.id == schedule_id).one_or_none()

            if schedule_orm is None:
                return None

            return models.Schedule.model_validate(schedule_orm)

    @retry()
    @exception_handler
    def get_schedule_by_hash(self, schedule_hash: str) -> models.Schedule | None:
        with self.dbconn.session.begin() as session:
            schedule_orm = (
                session.query(models.ScheduleDB).filter(models.ScheduleDB.hash == schedule_hash).one_or_none()
            )

            if schedule_orm is None:
                return None

            return models.Schedule.model_validate(schedule_orm)

    @retry()
    @exception_handler
    def create_schedule(self, schedule: models.Schedule) -> models.Schedule:
        with self.dbconn.session.begin() as session:
            schedule_orm = models.ScheduleDB(**schedule.model_dump())
            session.add(schedule_orm)

            created_schedule = models.Schedule.model_validate(schedule_orm)

            return created_schedule

    @retry()
    @exception_handler
    def update_schedule(self, schedule: models.Schedule) -> None:
        with self.dbconn.session.begin() as session:
            (
                session.query(models.ScheduleDB)
                .filter(models.ScheduleDB.id == schedule.id)
                .update(schedule.model_dump(exclude={"tasks"}))
            )

    @retry()
    @exception_handler
    def delete_schedule(self, schedule_id: str) -> None:
        with self.dbconn.session.begin() as session:
            session.query(models.ScheduleDB).filter(models.ScheduleDB.id == schedule_id).delete()
