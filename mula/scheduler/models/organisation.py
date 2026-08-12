from pydantic import BaseModel


class Organisation(BaseModel):
    id: str
    name: str | None = None
