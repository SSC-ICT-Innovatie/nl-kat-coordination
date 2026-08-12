from datetime import datetime

from pydantic import BaseModel


class Scheduler(BaseModel):
    id: str
    type: str
    item_type: str
    qsize: int = 0
    last_activity: datetime | None = None
