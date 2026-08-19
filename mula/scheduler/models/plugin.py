import datetime

from pydantic import BaseModel, Field, model_validator

from scheduler.models.ooi import RunOn


class Plugin(BaseModel):
    id: str
    type: str
    enabled: bool
    name: str | None = None
    version: str | None = None
    authors: list[str] | None = None
    created: datetime.datetime | None = None
    description: str | None = None
    related: list[str] | None = None
    scan_level: int | None = None
    consumes: str | list[str]
    options: list[str] | None = None
    produces: list[str]
    cron: str | None = None
    interval: int | None = None
    rate_limit_interval: float | None = Field(default=None, gt=0)
    rate_limit_group: str | None = None
    run_on: list[RunOn] | None = None
    oci_image: str | None = None
    oci_arguments: list[str] | None = None

    @model_validator(mode="after")
    def rate_limit_has_group(self):
        if self.rate_limit_interval is not None and not self.rate_limit_group:
            raise ValueError("rate_limit_group is required when rate_limit_interval is set")
        return self
