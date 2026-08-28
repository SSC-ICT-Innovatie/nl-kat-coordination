import enum
import uuid
from datetime import datetime, timezone
from typing import ClassVar

import mmh3
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.sql.schema import Index

from scheduler.utils import GUID

from .base import Base
from .boefje import Boefje
from .normalizer import Normalizer
from .raw_data import RawData


class TaskStatus(str, enum.Enum):
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
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    scheduler_id: str
    schedule_id: uuid.UUID | None = None
    organisation: str
    priority: int | None = 0
    status: TaskStatus = TaskStatus.PENDING
    type: str | None = None
    hash: str | None = Field(None, max_length=32)
    data: dict = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    modified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskDB(Base):
    __tablename__ = "tasks"

    id = Column(GUID, primary_key=True)
    scheduler_id = Column(String, nullable=False)
    schedule_id = Column(GUID, ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True)
    organisation = Column(String, nullable=False)
    type = Column(String, nullable=False)
    hash = Column(String(32), index=True)
    priority = Column(Integer)
    data = Column(JSONB, nullable=False)
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.PENDING)

    schedule = relationship("ScheduleDB", back_populates="tasks")

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    modified_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


Index("ix_tasks_status_queued", TaskDB.scheduler_id, TaskDB.status, postgresql_where=TaskDB.status == TaskStatus.QUEUED)


class NormalizerTask(BaseModel):
    """NormalizerTask represent data needed for a Normalizer to run."""

    type: ClassVar[str] = "normalizer"

    id: uuid.UUID | None = Field(default_factory=uuid.uuid4)
    normalizer: Normalizer
    raw_data: RawData

    @property
    def hash(self) -> str:
        """Make NormalizerTask hashable, so that we can de-duplicate it when
        used in the PriorityQueue. We hash the combination of the attributes
        normalizer.id since this combination is unique."""
        return mmh3.hash_bytes(
            f"{self.normalizer.id}-{self.raw_data.boefje_meta.id}-{self.raw_data.boefje_meta.organization}"
        ).hex()


class BoefjeTask(BaseModel):
    """BoefjeTask represent data needed for a Boefje to run."""

    type: ClassVar[str] = "boefje"

    id: uuid.UUID | None = Field(default_factory=uuid.uuid4)
    boefje: Boefje
    input_ooi: str | None = None
    organization: str
    deduplication_key: uuid.UUID | None = None

    dispatches: list[Normalizer] = Field(default_factory=list)

    @property
    def hash(self) -> str:
        """Make BoefjeTask hashable, so that we can de-duplicate it when used
        in the PriorityQueue. We hash the combination of the attributes
        input_ooi and boefje.id since this combination is unique."""
        if self.input_ooi:
            return mmh3.hash_bytes(f"{self.input_ooi}-{self.boefje.id}-{self.organization}").hex()

        return mmh3.hash_bytes(f"{self.boefje.id}-{self.organization}").hex()


class ReportTask(BaseModel):
    type: ClassVar[str] = "report"

    organisation_id: str
    report_recipe_id: str

    @property
    def hash(self) -> str:
        return mmh3.hash_bytes(f"{self.report_recipe_id}-{self.organisation_id}").hex()
