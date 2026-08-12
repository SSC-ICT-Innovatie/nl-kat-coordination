import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SchedulerType(str, enum.Enum):
    """Enum for scheduler types."""

    UNKNOWN = "unknown"
    BOEFJE = "boefje"
    NORMALIZER = "normalizer"
    REPORT = "report"


class Scheduler(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: str
    type: SchedulerType
    item_type: Any
    qsize: int = 0
    last_activity: datetime | None = None
