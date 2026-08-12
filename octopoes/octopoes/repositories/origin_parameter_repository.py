from datetime import datetime
from http import HTTPStatus
from typing import Any

from httpx import HTTPStatusError

from octopoes.events.events import OperationType, OriginParameterDBEvent
from octopoes.events.manager import EventManager
from octopoes.models import Reference
from octopoes.models.exception import ObjectNotFoundException
from octopoes.models.origin import OriginParameter
from octopoes.repositories.repository import Repository
from octopoes.xtdb import FieldSet
from octopoes.xtdb.client import OperationType as XTDBOperationType
from octopoes.xtdb.client import XTDBSession
from octopoes.xtdb.query_builder import generate_pull_query


class OriginParameterRepository(Repository):
    def __init__(self, event_manager: EventManager):
        self.event_manager = event_manager

    def get(self, origin_parameter_id: str, valid_time: datetime) -> OriginParameter:
        raise NotImplementedError

    def save(self, origin_parameter: OriginParameter, valid_time: datetime) -> None:
        raise NotImplementedError

    def delete(self, origin_parameter: OriginParameter, valid_time: datetime) -> None:
        raise NotImplementedError

    def list_by_origin(self, origin_id: set[str], valid_time: datetime) -> list[OriginParameter]:
        raise NotImplementedError

    def list_by_reference(self, reference: Reference, valid_time: datetime) -> list[OriginParameter]:
        raise NotImplementedError


class XTDBOriginParameterRepository(OriginParameterRepository):
    pk_prefix = "xt/id"

    def __init__(self, event_manager: EventManager, session: XTDBSession):
        super().__init__(event_manager)
        self.session = session

    def commit(self, sync: bool = False):
        self.session.commit(sync)

    @classmethod
    def serialize(cls, origin_parameter: OriginParameter) -> dict[str, Any]:
        data = origin_parameter.model_dump()
        data[cls.pk_prefix] = origin_parameter.id
        data["type"] = origin_parameter.__class__.__name__
        return data

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> OriginParameter:
        return OriginParameter.model_validate(data)

    def get(self, origin_parameter_id: str, valid_time: datetime) -> OriginParameter:
        try:
            return self.deserialize(self.session.client.get_entity(origin_parameter_id, valid_time))
        except HTTPStatusError as e:
            if e.response.status_code == HTTPStatus.NOT_FOUND:
                raise ObjectNotFoundException(origin_parameter_id)
            else:
                raise e

    def list_by_origin(self, origin_id: set[str], valid_time: datetime) -> list[OriginParameter]:
        query = generate_pull_query(FieldSet.ALL_FIELDS, {"origin_id": origin_id, "type": OriginParameter.__name__})
        results = self.session.client.query(query, valid_time=valid_time)
        return [self.deserialize(r[0]) for r in results]

    def list_by_reference(self, reference: Reference, valid_time: datetime) -> list[OriginParameter]:
        query = generate_pull_query(
            FieldSet.ALL_FIELDS, {"reference": str(reference), "type": OriginParameter.__name__}
        )
        results = self.session.client.query(query, valid_time=valid_time)
        return [self.deserialize(r[0]) for r in results]

    def save(self, origin_parameter: OriginParameter, valid_time: datetime) -> None:
        try:
            old_origin_parameter = self.get(origin_parameter.id, valid_time)
        except ObjectNotFoundException:
            old_origin_parameter = None

        if old_origin_parameter == origin_parameter:
            return

        self.session.add((XTDBOperationType.PUT, self.serialize(origin_parameter), valid_time))

        event = OriginParameterDBEvent(
            operation_type=OperationType.CREATE if old_origin_parameter is None else OperationType.UPDATE,
            valid_time=valid_time,
            old_data=old_origin_parameter,
            new_data=origin_parameter,
            client=self.event_manager.client,
        )
        self.session.listen_post_commit(lambda: self.event_manager.publish(event))

    def delete(self, origin_parameter: OriginParameter, valid_time: datetime) -> None:
        self.session.add((XTDBOperationType.DELETE, origin_parameter.id, valid_time))

        event = OriginParameterDBEvent(
            operation_type=OperationType.DELETE,
            valid_time=valid_time,
            old_data=origin_parameter,
            client=self.event_manager.client,
        )
        self.session.listen_post_commit(lambda: self.event_manager.publish(event))
