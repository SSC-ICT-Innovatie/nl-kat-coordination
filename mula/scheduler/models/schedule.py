import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.sql.schema import Index

from scheduler.utils import GUID, cron

from .base import Base


class Schedule(BaseModel):
    model_config = ConfigDict(from_attributes=True, validate_assignment=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    scheduler_id: str
    organisation: str
    hash: str | None = Field(None, max_length=32)
    data: dict | None = None
    enabled: bool = True
    schedule: str | None = None

    deadline_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    modified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, context) -> None:
        """Post init method to set the deadline_at if it is not set."""
        if self.deadline_at is None and self.schedule:
            self.deadline_at = cron.next_run(self.schedule)

    @field_validator("schedule")
    @classmethod
    def validate_schedule(cls, value: str) -> str:
        """Custom validation for the schedule cron expression."""
        if value is None:
            return value

        try:
            cron.next_run(value)
            return value
        except Exception as exc:
            raise ValueError(f"Invalid cron expression: {value}") from exc


class ScheduleDB(Base):
    __tablename__ = "schedules"

    id = Column(GUID, primary_key=True)
    scheduler_id = Column(String, nullable=False)
    organisation = Column(String, nullable=False)
    hash = Column(String(32), nullable=True, unique=True)
    data = Column(JSONB, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    schedule = Column(String, nullable=True)
    tasks = relationship("TaskDB", back_populates="schedule")

    deadline_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    modified_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

Index("ix_schedules_enabled", ScheduleDB.enabled)
Index("ix_schedules_hash", ScheduleDB.hash)
Index("ix_schedules_organisation", ScheduleDB.organisation)
Index("ix_schedules_scheduler_id", ScheduleDB.scheduler_id)
