import uuid
from typing import Any, ClassVar

import mmh3
import pydantic
from scheduler import models
from scheduler.server import schemas
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Query

from tests import factories


class TestModel(pydantic.BaseModel):
    type: ClassVar[str] = "test-model"
    id: str
    name: str
    count: int = 0
    categories: list[str] | None = None
    child: Any = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        if self.categories is None:
            self.categories = []

    @property
    def hash(self) -> str:
        return mmh3.hash_bytes(f"{self.id}-{self.name}").hex()


def create_test_model() -> TestModel:
    return TestModel(id=uuid.uuid4().hex, name=uuid.uuid4().hex)


def create_task_push(priority: int, organisation: str, data: TestModel | None = None) -> schemas.TaskPush:
    if data is None:
        data = TestModel(id=uuid.uuid4().hex, name=uuid.uuid4().hex)

    return schemas.TaskPush(priority=priority, organisation=organisation, data=data.model_dump())


def create_task_push_dict(priority: int, organisation: str, data: TestModel | None = None) -> dict[str, Any]:
    return create_task_push(priority, organisation, data).model_dump(exclude_none=True)


def create_schedule(scheduler_id: str, data: Any | None = None) -> models.Schedule:
    item = data or create_test_model()
    return models.Schedule(scheduler_id=scheduler_id, hash=item.hash, data=item.model_dump())


def create_task(scheduler_id: str, organisation: str, priority: int = 0, data: Any | None = None) -> models.Task:
    if data is None:
        data = TestModel(id=uuid.uuid4().hex, name=uuid.uuid4().hex)

    return models.Task(
        scheduler_id=scheduler_id,
        organisation=organisation,
        priority=priority,
        type=TestModel.type,
        hash=data.hash,
        data=data.model_dump(),
    )


def create_boefje() -> models.Boefje:
    scan_profile = factories.ScanProfileFactory(level=0)
    ooi = factories.OOIFactory(scan_profile=scan_profile)
    return factories.PluginFactory(scan_level=0, consumes=[ooi.object_type])


def compile_query(query: Query) -> str:
    return str(query.statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
