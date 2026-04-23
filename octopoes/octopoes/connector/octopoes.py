import json
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

import httpx
import structlog
from httpx import HTTPError, Response
from pydantic import Field, TypeAdapter, ValidationError

from octopoes.api.models import Affirmation, Declaration, Observation, ServiceHealth
from octopoes.config.settings import DEFAULT_LIMIT, DEFAULT_OFFSET
from octopoes.connector import DecodeException, RemoteException
from octopoes.models import OOI, Reference, ScanLevel, ScanProfile, ScanProfileType
from octopoes.models.exception import ObjectNotFoundException
from octopoes.models.explanation import InheritanceSection
from octopoes.models.ooi.findings import Finding, RiskLevelSeverity
from octopoes.models.ooi.reports import HydratedReport
from octopoes.models.origin import Origin, OriginParameter, OriginType
from octopoes.models.pagination import Paginated
from octopoes.models.transaction import TransactionRecord
from octopoes.models.tree import ReferenceTree
from octopoes.models.types import OOIType, type_by_name
from octopoes.types import AFFIRMATION_CREATED, DECLARATION_CREATED, OBJECT_DELETED, OBSERVATION_CREATED, ORIGIN_DELETED

QueryTypeAdapter = TypeAdapter(OOIType | str)
QueryManyTypeAdapter = TypeAdapter(list[tuple[str, OOIType | str]])
HydratedReportsTypeAdapter = TypeAdapter(dict[UUID, HydratedReport])
PaginatedOOITypeAdapter = TypeAdapter(Paginated[Annotated[OOIType, Field(discriminator="object_type")]])
PaginatedFindingTypeAdapter = TypeAdapter(Paginated[Annotated[Finding, Field(discriminator="object_type")]])
TransactionRecordTypeAdapter = TypeAdapter(list[TransactionRecord])
OriginTypeAdapter = TypeAdapter(list[Origin])
OriginParameterTypeAdapter = TypeAdapter(list[OriginParameter])
HydratedReportTypeAdapter = TypeAdapter(HydratedReport)
PaginatedHydratedReportsTypeAdapter = TypeAdapter(Paginated[HydratedReport])
ObjectsTypeAdapter = TypeAdapter(dict[str, Annotated[OOIType, Field(discriminator="object_type")]])
ObjectsDictTypeAdapter = TypeAdapter(dict[Reference, Annotated[OOIType, Field(discriminator="object_type")]])
ScanprofilesListTypeAdapter = TypeAdapter(list[InheritanceSection])
DeclarationsTypeAdapter = TypeAdapter(list[Declaration])


class OctopoesAPIConnector:
    """
    Methods on this Connector can throw
        - httpx.HTTPError if HTTP connection to Octopoes API fails
        - connector.ObjectNotFoundException if the OOI node cannot be found
        - connector.RemoteException if an error occurs inside Octopoes API
    """

    def __init__(self, base_uri: str, client: str, timeout: int = 30):
        self.base_uri = base_uri
        self.client = client
        self.session = httpx.Client(
            base_url=base_uri, timeout=timeout, event_hooks={"response": [self._verify_response]}
        )
        self.logger = structlog.get_logger("octopoes-connector", organisation_code=client)

    @staticmethod
    def _verify_response(response: Response) -> None:
        try:
            response.read()  # read the response body before raising an exception
            response.raise_for_status()
        except HTTPError as error:
            if response.status_code == 404:
                data = response.json()
                raise ObjectNotFoundException(data["detail"]) from error
            if 500 <= response.status_code < 600:
                data = response.content  # handles unicode issues
                raise RemoteException(value=data) from error
            raise
        except json.decoder.JSONDecodeError as error:
            raise DecodeException("JSON decode error") from error

    def root_health(self) -> ServiceHealth:
        return ServiceHealth.model_validate_json(self.session.get("/health").content)

    def health(self) -> ServiceHealth:
        return ServiceHealth.model_validate_json(self.session.get(f"/{self.client}/health").content)

    def list_objects(
        self,
        types: set[type[OOI]] | set[str],
        valid_time: datetime,
        offset: int = DEFAULT_OFFSET,
        limit: int = DEFAULT_LIMIT,
        scan_level: set[ScanLevel] | set[int] | None = None,
        scan_profile_type: set[ScanProfileType] | set[str] | None = None,
        search_string: str | None = None,
        order_by: Literal["scan_level", "object_type"] = "object_type",
        asc_desc: Literal["asc", "desc"] = "asc",
    ) -> Paginated[OOIType]:
        params: dict[str, str | int | list[str] | list[int] | None] = {
            "types": [t.__name__ if hasattr(t, "__name__") else t for t in types if t],
            "valid_time": str(valid_time),
            "offset": offset,
            "limit": limit,
            "order_by": order_by,
            "asc_desc": asc_desc,
        }

        if scan_level:
            scan_levels: list[int] = []
            for slevel in scan_level:
                if isinstance(slevel, int):
                    scan_levels.append(slevel)
                else:
                    scan_levels.append(slevel.value)
            params["scan_level"] = scan_levels
        if scan_profile_type:
            scan_profile_types: list[str] = []
            for sprofile in scan_profile_type:
                if isinstance(sprofile, str):
                    scan_profile_types.append(sprofile)
                else:
                    scan_profile_types.append(sprofile.value)
            params["scan_profile_type"] = scan_profile_types
        if search_string:
            params["search_string"] = search_string
        params = {k: v for k, v in params.items() if v is not None}  # filter out None values
        res = self.session.get(f"/{self.client}/objects", params=params)
        return PaginatedOOITypeAdapter.validate_json(res.content)

    def get(self, reference: Reference, valid_time: datetime) -> OOIType:
        res = self.session.get(
            f"/{self.client}/object", params={"reference": str(reference), "valid_time": str(valid_time)}
        )
        objectjson = res.json()
        objecttypename = objectjson.get("object_type", None)
        try:
            if not objecttypename:
                raise ValidationError(
                    f"JSON from Octopoes for `{reference}`@{valid_time}  did not contain 'object_type' property."
                )
            objecttype: type[OOI] = type_by_name(objecttypename)
            instance: OOIType = objecttype.model_validate(objectjson)
            return instance
        except ValidationError as error:
            self.logger.error(
                "Could not validate OOI: `%s` against schema of type: `%s`",
                objectjson.get("primary_key", "unknown-primary-key"),
                objecttypename or "Unknown Object type",
                objectdata=objectjson,
                error=error,
            )
            raise

    def get_history(
        self,
        reference: Reference,
        *,
        sort_order: str = "asc",  # Or: "desc"
        with_docs: bool = False,
        has_doc: bool | None = None,
        offset: int = 0,
        limit: int | None = None,
        indices: list[int] | None = None,
    ) -> list[TransactionRecord]:
        params: dict[str, str | int | list[int] | None] = {
            "reference": str(reference),
            "sort_order": sort_order,
            "with_docs": with_docs,
            "has_doc": has_doc,
            "offset": offset,
            "limit": limit,
            "indices": indices,
        }
        params = {k: v for k, v in params.items() if v is not None}  # filter out None values
        res = self.session.get(f"/{self.client}/object-history", params=params)
        return TransactionRecordTypeAdapter.validate_json(res.content)

    def get_tree(
        self,
        reference: Reference,
        valid_time: datetime,
        types: set[type[OOI]] | set[str] | None = None,
        depth: int = 1,
        with_scan_profiles: bool | None = True,
    ) -> ReferenceTree:
        params: dict[str, str | int | list[str]] = {
            "reference": str(reference),
            "depth": depth,
            "valid_time": str(valid_time),
            "with_scan_profiles": "false",
        }
        if with_scan_profiles:
            params["with_scan_profiles"] = "true"
        if types:
            params["types"] = [t.__name__ if hasattr(t, "__name__") else t for t in types if t]
        res = self.session.get(f"/{self.client}/tree", params=params)
        return ReferenceTree.model_validate_json(res.content)

    def list_origins(
        self,
        valid_time: datetime,
        offset: int = DEFAULT_OFFSET,
        limit: int = DEFAULT_LIMIT,
        source: Reference | None = None,
        result: Reference | None = None,
        method: str | list[str] | None = None,
        task_id: UUID | None = None,
        origin_type: OriginType | None = None,
    ) -> list[Origin]:
        params = {
            "valid_time": str(valid_time),
            "source": source,
            "result": result,
            "offset": offset,
            "limit": limit,
            "method": method,
            "task_id": str(task_id) if task_id else None,
            "origin_type": str(origin_type.value) if origin_type else None,
        }
        params = {k: v for k, v in params.items() if v is not None}  # filter out None values
        res = self.session.get(f"/{self.client}/origins", params=params)

        return OriginTypeAdapter.validate_json(res.content)

    def delete_origin(self, origin_id: str, valid_time: datetime, sync: bool = False) -> None:
        params = {"valid_time": str(valid_time), "origin_id": origin_id}
        if sync:
            params["sync"] = "true"
        self.session.delete(f"/{self.client}/origins", params=params)

        self.logger.info(
            "Deleted origin", origin_id=origin_id, valid_time=valid_time, event_code=ORIGIN_DELETED, sync=sync
        )

    def save_observation(self, observation: Observation, sync: bool = False) -> None:
        params = {}
        if sync:
            params["sync"] = "true"
        self.session.post(f"/{self.client}/observations", params=params, json=observation.model_dump(mode="json"))

        self.logger.info("Saved observation", observation=observation, event_code=OBSERVATION_CREATED, sync=sync)

    def save_declaration(self, declaration: Declaration, sync: bool = False) -> None:
        params = {}
        if sync:
            params["sync"] = "true"
        self.session.post(f"/{self.client}/declarations", params=params, json=declaration.model_dump(mode="json"))

        self.logger.info("Saved declaration", declaration=declaration, event_code=DECLARATION_CREATED, sync=sync)

    def save_many_declarations(self, declarations: list[Declaration], sync: bool = False) -> None:
        params = {}
        if sync:
            params["sync"] = "true"
        self.session.post(
            f"/{self.client}/declarations/save_many",
            params=params,
            json=DeclarationsTypeAdapter.dump_python(declarations, mode="json"),
        )

        self.logger.info("Saved %s declarations", len(declarations), event_code=DECLARATION_CREATED, sync=sync)

    def save_affirmation(self, affirmation: Affirmation, sync: bool = False) -> None:
        params = {}
        if sync:
            params["sync"] = "true"
        self.session.post(f"/{self.client}/affirmations", params=params, json=affirmation.model_dump(mode="json"))

        self.logger.info("Saved affirmation", affirmation=affirmation, event_code=AFFIRMATION_CREATED, sync=sync)

    def save_scan_profile(self, scan_profile: ScanProfile, valid_time: datetime, sync: bool = False) -> None:
        params = {"valid_time": str(valid_time)}
        if sync:
            params["sync"] = "true"
        self.session.put(f"/{self.client}/scan_profiles", params=params, json=scan_profile.model_dump(mode="json"))

        self.logger.info("Saved Scan profile", scan_profile=scan_profile, valid_time=valid_time, sync=sync)

    def save_many_scan_profiles(
        self, scan_profiles: list[ScanProfile], valid_time: datetime, sync: bool = False
    ) -> None:
        params = {"valid_time": str(valid_time)}
        if sync:
            params["sync"] = "true"
        self.session.post(
            f"/{self.client}/scan_profiles/save_many",
            params=params,
            json=[scan_profile.model_dump(mode="json") for scan_profile in scan_profiles],
        )

    def delete(self, reference: Reference, valid_time: datetime, sync: bool = False) -> None:
        params = {"reference": str(reference), "valid_time": str(valid_time)}
        if sync:
            params["sync"] = "true"
        self.session.delete(f"/{self.client}/", params=params)

        self.logger.info(
            "Deleted object", reference=reference, valid_time=valid_time, event_code=OBJECT_DELETED, sync=sync
        )

    def delete_many(self, references: list[Reference], valid_time: datetime, sync: bool = False) -> None:
        params = {"valid_time": str(valid_time)}
        if sync:
            params["sync"] = "true"
        self.session.post(f"/{self.client}/objects/delete_many", params=params, json=[str(ref) for ref in references])

        self.logger.info(
            "Deleted objects", references=references, valid_time=valid_time, event_code=OBJECT_DELETED, sync=sync
        )

    def list_origin_parameters(self, origin_id: set[str], valid_time: datetime) -> list[OriginParameter]:
        params = {"origin_id": list(origin_id), "valid_time": str(valid_time)}
        res = self.session.get(f"/{self.client}/origin_parameters", params=params)
        return OriginParameterTypeAdapter.validate_json(res.content)

    def create_node(self):
        self.session.post(f"/{self.client}/node")

        self.logger.info("Created node")

    def delete_node(self):
        self.session.delete(f"/{self.client}/node")

        self.logger.info("Deleted node")

    def get_scan_profile_inheritance(self, reference: Reference, valid_time: datetime) -> list[InheritanceSection]:
        params = {"reference": str(reference), "valid_time": str(valid_time)}
        res = self.session.get(f"/{self.client}/scan_profiles/inheritance", params=params)
        return ScanprofilesListTypeAdapter.validate_json(res.content)

    def count_findings_by_severity(self, valid_time: datetime) -> dict[str, int]:
        params = {"valid_time": str(valid_time)}
        res = self.session.get(f"/{self.client}/findings/count_by_severity", params=params)
        return res.json()

    def list_findings(
        self,
        severities: Iterable[RiskLevelSeverity],
        valid_time: datetime,
        exclude_muted: bool = True,
        only_muted: bool = False,
        offset: int = DEFAULT_OFFSET,
        limit: int = DEFAULT_LIMIT,
        search_string: str | None = None,
        order_by: Literal["score", "finding_type"] = "score",
        asc_desc: Literal["asc", "desc"] = "desc",
    ) -> Paginated[Finding]:
        params: dict[str, str | int | list[str] | None] = {
            "valid_time": str(valid_time),
            "offset": offset,
            "limit": limit,
            "severities": [s.value for s in severities],
            "exclude_muted": exclude_muted,
            "only_muted": only_muted,
            "order_by": order_by,
            "asc_desc": asc_desc,
        }
        if search_string:
            params["search_string"] = search_string

        params = {k: v for k, v in params.items() if v is not None}  # filter out None values
        res = self.session.get(f"/{self.client}/findings", params=params)
        return PaginatedFindingTypeAdapter.validate_json(res.content)

    def list_reports(
        self,
        valid_time: datetime,
        offset: int = DEFAULT_OFFSET,
        limit: int = DEFAULT_LIMIT,
        recipe_id: UUID | None = None,
    ) -> Paginated[HydratedReport]:
        params: dict[str, str | int] = {"valid_time": str(valid_time), "offset": offset, "limit": limit}

        if recipe_id:
            params["recipe_id"] = recipe_id.hex

        res = self.session.get(f"/{self.client}/reports", params=params)

        return PaginatedHydratedReportsTypeAdapter.validate_json(res.content)

    def bulk_list_reports(
        self, valid_time: datetime, reports_filters: list[tuple[str, str]]
    ) -> dict[UUID, HydratedReport]:
        """
        Return HydratedReport over multiple clients.
        The reports_filter is a list of tuples of (client, recipe_id).
        """
        res = self.session.post("/reports", json=reports_filters, params={"valid_time": str(valid_time)})

        return HydratedReportsTypeAdapter.validate_json(res.content)

    def list_object_clients(self, reference: Reference, clients: set[str], valid_time: datetime) -> dict[str, OOIType]:
        """
        Return the clients from the provided list that have the given OOI at the valid_time.
        """
        res = self.session.get(
            "/object-clients", params={"reference": reference, "clients": list(clients), "valid_time": str(valid_time)}
        )

        return ObjectsTypeAdapter.validate_json(res.content)

    def get_report(self, report_id: str, valid_time: datetime) -> HydratedReport:
        params = {"valid_time": str(valid_time)}

        res = self.session.get(f"/{self.client}/reports/{report_id}", params=params)

        return HydratedReportTypeAdapter.validate_json(res.content)

    def load_objects_bulk(
        self, references: set[Reference], valid_time: datetime, with_scan_profiles: bool | None = True
    ) -> dict[Reference, OOIType]:
        params = {"valid_time": str(valid_time), "with_scan_profiles": "false"}
        if with_scan_profiles:
            params["with_scan_profiles"] = "true"
        res = self.session.post(
            f"/{self.client}/objects/load_bulk", params=params, json=[str(ref) for ref in references]
        )
        return ObjectsDictTypeAdapter.validate_json(res.content)

    def recalculate_bits(self) -> int:
        return self.session.post(f"/{self.client}/bits/recalculate").json()

    def query(
        self,
        path: str,
        valid_time: datetime,
        source: OOI | Reference | str | None = None,
        offset: int = DEFAULT_OFFSET,
        limit: int = DEFAULT_LIMIT,
    ) -> list[OOI]:
        params = {
            "path": path,
            "source": source.reference if isinstance(source, OOI) else source,
            "valid_time": str(valid_time),
            "offset": offset,
            "limit": limit,
        }
        params = {k: v for k, v in params.items() if v is not None}  # filter out None values

        return [
            QueryTypeAdapter.validate_python(ooi)
            for ooi in self.session.get(f"/{self.client}/query", params=params).json()
        ]

    def query_many(
        self, path: str, valid_time: datetime, sources: Sequence[OOI | Reference | str]
    ) -> list[tuple[str, OOIType]]:
        if not sources:
            return []

        params = {"path": path, "sources": [str(ooi) for ooi in sources], "valid_time": str(valid_time)}

        result = self.session.get(f"/{self.client}/query-many", params=params).json()

        return QueryManyTypeAdapter.validate_python(result)

    def export_all(self):
        return self.session.get(f"/{self.client}/io/export").json()

    def import_add(self, content):
        return self.session.post(f"/{self.client}/io/import/add", content=content).json()

    def import_new(self, content):
        return self.session.post(f"/{self.client}/io/import/new", content=content).json()

    def _bulk_migrate_origins(self, origins: list[Origin], valid_time: datetime) -> None:
        """Single-purpose method that should not be used outside the migration, hence private"""

        params = {"valid_time": str(valid_time)}
        self.session.post(
            f"/{self.client}/origins/migrate", params=params, json=[x.model_dump(mode="json") for x in origins]
        )
