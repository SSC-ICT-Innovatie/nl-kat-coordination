from typing import Any

from pydantic import BaseModel, Field


class ServiceHealth(BaseModel):
    """ServiceHealth is used as response model for health check in the
    server.Server for the health endpoint.
    """

    service: str
    healthy: bool = False
    version: str | None = None
    additional: Any = None
    results: list["ServiceHealth"] = Field(default_factory=list)
    externals: dict[str, bool] = {}


ServiceHealth.model_rebuild()
