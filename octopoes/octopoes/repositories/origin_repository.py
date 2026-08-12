from datetime import datetime
from http import HTTPStatus
from typing import Any
from uuid import UUID

from httpx import HTTPStatusError

from octopoes.events.events import OperationType, OriginDBEvent
from octopoes.events.manager import EventManager
from octopoes.models import Reference
from octopoes.models.exception import ObjectNotFoundException
from octopoes.models.origin import Origin, OriginType
from octopoes.repositories.repository import Repository
from octopoes.xtdb import FieldSet
from octopoes.xtdb.client import OperationType as XTDBOperationType
from octopoes.xtdb.client import XTDBSession
from octopoes.xtdb.query_builder import generate_pull_query


class OriginRepository(Repository):
    def __init__(self, event_manager: EventManager):
        self.event_manager = event_manager

    def get(self, origin_id: str, valid_time: datetime) -> Origin:
        raise NotImplementedError

    def save(self, origin: Origin, valid_time: datetime) -> None:
        raise NotImplementedError

    def list_origins(
        self,
        valid_time: datetime,
        *,
        task_id: UUID | None = None,
        offset: int = 0,
        limit: int | None = None,
        source: Reference | None = None,
        result: Reference | None = None,
        method: str | list[str] | None = None,
        origin_type: OriginType | list[OriginType] | set[OriginType] | None = None,
    ) -> list[Origin]:
        raise NotImplementedError

    def delete(self, origin: Origin, valid_time: datetime) -> None:
        raise NotImplementedError


class XTDBOriginRepository(OriginRepository):
    pk_prefix = "xt/id"

    def __init__(self, event_manager: EventManager, session: XTDBSession):
        super().__init__(event_manager)
        self.session = session

    def commit(self, sync: bool = False):
        self.session.commit(sync)

    @classmethod
    def serialize(cls, origin: Origin) -> dict[str, Any]:
        data = origin.model_dump()
        data[cls.pk_prefix] = origin.id
        data["type"] = origin.__class__.__name__
        data["result"] = list(dict.fromkeys(data["result"]))
        return data

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> Origin:
        return Origin.model_validate(data)

    def list_origins(
        self,
        valid_time: datetime,
        *,
        task_id: UUID | None = None,
        offset: int = 0,
        limit: int | None = None,
        source: Reference | None = None,
        result: Reference | None = None,
        method: str | list[str] | None = None,
        origin_type: OriginType | list[OriginType] | set[OriginType] | None = None,
    ) -> list[Origin]:
        where_parameters: dict[str, str | list[str]] = {"type": Origin.__name__}

        if task_id:
            where_parameters["task_id"] = str(task_id)

        if source:
            where_parameters["source"] = str(source)

        if result:
            where_parameters["result"] = str(result)

        if method:
            where_parameters["method"] = method

        if origin_type:
            if isinstance(origin_type, OriginType):
                where_parameters["origin_type"] = origin_type.value
            elif isinstance(origin_type, list | set) and all(isinstance(otype, OriginType) for otype in origin_type):
                where_parameters["origin_type"] = [otype.value for otype in origin_type]

        query = generate_pull_query(FieldSet.ALL_FIELDS, where_parameters, offset=offset, limit=limit)

        results = self.session.client.query(query, valid_time=valid_time)
        return [self.deserialize(r[0]) for r in results]

    def get(self, id_: str, valid_time: datetime) -> Origin:
        try:
            return self.deserialize(self.session.client.get_entity(id_, valid_time))
        except HTTPStatusError as e:
            if e.response.status_code == HTTPStatus.NOT_FOUND:
                raise ObjectNotFoundException(id_)
            else:
                raise e

    def save(self, origin: Origin, valid_time: datetime) -> None:
        try:
            old_origin = self.get(origin.id, valid_time)
        except ObjectNotFoundException:
            old_origin = None

        if old_origin == origin:
            # Declared and inferred origins won't have a task id, so if the old
            # origin is the same as the one being saved we can just return. In
            # case an observed origin is saved, we will delete the origin with
            # the old task id and create a new one. We can still fetch the old
            # origin using the previous valid time.
            if origin.task_id == old_origin.task_id:
                return

            self.session.add((XTDBOperationType.DELETE, old_origin.id, valid_time))

        self.session.add((XTDBOperationType.PUT, self.serialize(origin), valid_time))
        if old_origin != origin:
            # Only publish an event if there is a change in data. We won't send
            # events when only the normalizer task id of an observed origin is
            # updated.
            event = OriginDBEvent(
                operation_type=OperationType.CREATE if old_origin is None else OperationType.UPDATE,
                valid_time=valid_time,
                old_data=old_origin,
                new_data=origin,
                client=self.event_manager.client,
            )
            self.session.listen_post_commit(lambda: self.event_manager.publish(event))

    def delete(self, origin: Origin, valid_time: datetime) -> None:
        self.session.add((XTDBOperationType.DELETE, origin.id, valid_time))

        event = OriginDBEvent(
            operation_type=OperationType.DELETE,
            valid_time=valid_time,
            old_data=origin,
            client=self.event_manager.client,
        )
        self.session.listen_post_commit(lambda: self.event_manager.publish(event))
