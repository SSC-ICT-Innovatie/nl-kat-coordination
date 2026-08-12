from datetime import datetime, timedelta, timezone
from typing import Any

from factory import Factory, Faker
from scheduler.models import Boefje, BoefjeMeta


class BoefjeFactory(Factory):
    class Meta:
        model = Boefje

    id: str = Faker("uuid4")
    name: str = Faker("name")
    description: str = Faker("text")


class BoefjeMetaFactory(Factory):
    class Meta:
        model = BoefjeMeta

    id: str = Faker("uuid4")
    arguments: dict[str, Any] = {}
    organization: str = Faker("company")
    started_at: datetime = datetime.now(timezone.utc) - timedelta(days=2)
    ended_at: datetime = datetime.now(timezone.utc) - timedelta(days=2)
