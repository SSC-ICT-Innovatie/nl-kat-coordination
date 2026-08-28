import json
import uuid
from collections import Counter
from collections.abc import Generator
from datetime import datetime
from operator import itemgetter
from typing import Any, Literal

import structlog
from asgiref.sync import sync_to_async
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request, status
from httpx import HTTPError
from pydantic import AwareDatetime

from octopoes.api.models import ServiceHealth, ValidatedAffirmation, ValidatedDeclaration, ValidatedObservation
from octopoes.config.settings import (
    DEFAULT_LIMIT,
    DEFAULT_OFFSET,
    DEFAULT_SCAN_LEVEL_FILTER,
    DEFAULT_SCAN_PROFILE_TYPE_FILTER,
    DEFAULT_SEVERITY_FILTER,
    Settings,
)
from octopoes.core.app import bootstrap_octopoes, get_xtdb_client
from octopoes.core.service import OctopoesService
from octopoes.models import OOI, Reference, ScanLevel, ScanProfile, ScanProfileBase, ScanProfileType
from octopoes.models.exception import ObjectNotFoundException
from octopoes.models.explanation import InheritanceSection
from octopoes.models.ooi.findings import Finding, RiskLevelSeverity
from octopoes.models.ooi.reports import HydratedReport
from octopoes.models.origin import Origin, OriginParameter, OriginType
from octopoes.models.pagination import Paginated
from octopoes.models.path import Path as ObjectPath
from octopoes.models.transaction import TransactionRecord
from octopoes.models.tree import ReferenceTree
from octopoes.models.types import type_by_name
from octopoes.repositories.origin_repository import XTDBOriginRepository
from octopoes.version import __version__
from octopoes.xtdb.client import Operation, OperationType, XTDBSession
from octopoes.xtdb.exceptions import XTDBException
from octopoes.xtdb.query import Aliased
from octopoes.xtdb.query import Query as XTDBQuery

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/{client}")


# Dependencies
def extract_client(client: str = Path(...)) -> str:
    return client


def extract_valid_time(valid_time: AwareDatetime) -> datetime:
    return valid_time


def extract_types(types: list[str] = Query(["OOI"])) -> set[type[OOI]]:
    try:
        return {type_by_name(t) for t in types}
    except KeyError as e:
        raise ObjectNotFoundException(str(e.args))


def extract_reference(reference: str = Query("")) -> Reference:
    return Reference.from_str(reference)


def extract_references(references: list[str]) -> list[Reference]:
    return [Reference.from_str(reference) for reference in references]


def settings() -> Settings:
    return Settings()


def xtdb_session(
    client: str = Depends(extract_client), settings_: Settings = Depends(settings)
) -> Generator[XTDBSession, None, None]:
    yield XTDBSession(get_xtdb_client(str(settings_.xtdb_uri), client))


def octopoes_service(
    client: str = Depends(extract_client),
    session: XTDBSession = Depends(xtdb_session),
    settings_: Settings = Depends(settings),
) -> OctopoesService:
    return bootstrap_octopoes(settings_, client, session)


# Endpoints
@router.get("/health")
def health(xtdb_session_: XTDBSession = Depends(xtdb_session)) -> ServiceHealth:
    try:
        xtdb_status = xtdb_session_.client.status()
        xtdb_health = ServiceHealth(service="xtdb", healthy=True, version=xtdb_status.version, additional=xtdb_status)
    except HTTPError as ex:
        xtdb_health = ServiceHealth(
            service="xtdb", healthy=False, additional="Cannot connect to XTDB at. Service possibly down"
        )
        logger.exception(ex)
    return ServiceHealth(service="octopoes", healthy=xtdb_health.healthy, version=__version__, results=[xtdb_health])


# OOI-related endpoints
@router.get("/objects", tags=["Objects"])
def list_objects(
    octopoes: OctopoesService = Depends(octopoes_service),
    valid_time: datetime = Depends(extract_valid_time),
    types: set[type[OOI]] = Depends(extract_types),
    scan_level: set[ScanLevel] = Query(DEFAULT_SCAN_LEVEL_FILTER),
    scan_profile_type: set[ScanProfileType] = Query(DEFAULT_SCAN_PROFILE_TYPE_FILTER),
    offset: int = 0,
    limit: int = 20,
    search_string: str | None = None,
    order_by: Literal["scan_level", "object_type"] = "object_type",
    asc_desc: Literal["asc", "desc"] = "asc",
):
    return octopoes.list_ooi(
        types, valid_time, offset, limit, scan_level, scan_profile_type, search_string, order_by, asc_desc
    )


@router.get("/query", tags=["Objects"])
def query(
    path: str,
    source: Reference | None = None,
    octopoes: OctopoesService = Depends(octopoes_service),
    valid_time: datetime = Depends(extract_valid_time),
    offset: int = DEFAULT_OFFSET,
    limit: int = DEFAULT_LIMIT,
):
    object_path = ObjectPath.parse(path)
    xtdb_query = XTDBQuery.from_path(object_path).offset(offset).limit(limit)

    if source is not None and object_path.segments:
        xtdb_query = xtdb_query.where(object_path.segments[0].source_type, primary_key=str(source))

    return octopoes.ooi_repository.query(xtdb_query, valid_time)


@router.get("/query-many", tags=["Objects"])
def query_many(
    path: str,
    sources: list[str] = Query(),
    octopoes: OctopoesService = Depends(octopoes_service),
    valid_time: datetime = Depends(extract_valid_time),
):
    """
    How does this work and why do we do this?

    We want to fetch all results but be able to tie these back to the source that was used for a result.
    If we query "Network.hostname" for a list of Networks ids, how do we know which hostname lives on which network?
    The answer is to add the network id to the "select" statement, so the result is of the form

        [(network_id_1, hostname1), (network_id_2, hostname3), ...]

    Because you can only select variables in Datalog, "network_id_1" needs to be an Alias. Hence `source_alias`.
    We need to tie that to the Network primary_key and add a where-in clause. The example projected on the code:

    q = XTDBQuery.from_path(object_path)                                    # Adds "where ?Hostname.network = ?Network

    q.find(source_alias).pull(query.result_type)                            # "select ?network_id, ?Hostname
     .where(object_path.segments[0].source_type, primary_key=source_alias)  # where ?Network.primary_key = ?network_id
     .where_in(object_path.segments[0].source_type, primary_key=sources)    # and ?Network.primary_key in ["1", ...]"
    """

    if not sources:
        return []

    object_path = ObjectPath.parse(path)
    if not object_path.segments:
        raise HTTPException(status_code=400, detail="No path components provided.")

    q = XTDBQuery.from_path(object_path)
    source_alias = Aliased(object_path.segments[0].source_type, field="primary_key")

    q = q.where(object_path.segments[0].source_type, primary_key=source_alias).where_in(
        object_path.segments[0].source_type, primary_key=sources
    )

    if q._find_clauses:  # Path contained a target field, so no need to pull the result type
        return octopoes.ooi_repository.query(q.find(source_alias, index=0), valid_time)

    return octopoes.ooi_repository.query(q.find(source_alias, index=0).pull(q.result_type), valid_time)


@router.post("/objects/load_bulk", tags=["Objects"])
def load_objects_bulk(
    octopoes: OctopoesService = Depends(octopoes_service),
    valid_time: datetime = Depends(extract_valid_time),
    references: set[Reference] = Depends(extract_references),
):
    return octopoes.ooi_repository.load_bulk(references, valid_time)


@router.get("/object", tags=["Objects"])
def get_object(
    octopoes: OctopoesService = Depends(octopoes_service),
    valid_time: datetime = Depends(extract_valid_time),
    reference: Reference = Depends(extract_reference),
):
    return octopoes.get_ooi(reference, valid_time)


@router.get("/object-history", tags=["Objects"])
def get_object_history(
    reference: Reference = Depends(extract_reference),
    sort_order: str = "asc",  # Or: "desc"
    with_docs: bool = False,
    has_doc: bool | None = None,
    offset: int = 0,
    limit: int | None = None,
    indices: list[int] | None = Query(None),
    octopoes: OctopoesService = Depends(octopoes_service),
) -> list[TransactionRecord]:
    return octopoes.get_ooi_history(
        reference,
        sort_order=sort_order,
        with_docs=with_docs,
        has_doc=has_doc,
        offset=offset,
        limit=limit,
        indices=indices,
    )


@router.get("/objects/random", tags=["Objects"])
def list_random_objects(
    octopoes: OctopoesService = Depends(octopoes_service),
    valid_time: datetime = Depends(extract_valid_time),
    amount: int = 1,
    scan_level: set[ScanLevel] = Query(DEFAULT_SCAN_LEVEL_FILTER),
):
    return octopoes.list_random_ooi(valid_time, amount, scan_level)


@router.delete("/", tags=["Objects"])
def delete_object(
    octopoes: OctopoesService = Depends(octopoes_service),
    valid_time: datetime = Depends(extract_valid_time),
    reference: Reference = Depends(extract_reference),
) -> None:
    octopoes.ooi_repository.delete(reference, valid_time)
    octopoes.commit()


@router.delete("/origins", tags=["Origins"])
def delete_origin(
    origin_id: str,
    octopoes: OctopoesService = Depends(octopoes_service),
    valid_time: datetime = Depends(extract_valid_time),
) -> None:
    origin = octopoes.origin_repository.get(origin_id, valid_time)
    octopoes.origin_repository.delete(origin, valid_time)
    octopoes.commit()


@router.post("/objects/delete_many", tags=["Objects"])
def delete_many(
    octopoes: OctopoesService = Depends(octopoes_service),
    valid_time: datetime = Depends(extract_valid_time),
    references: list[Reference] = Depends(extract_references),
) -> None:
    for reference in references:
        octopoes.ooi_repository.delete(reference, valid_time)

    octopoes.commit()


@router.get("/tree", tags=["Objects"])
def get_tree(
    octopoes: OctopoesService = Depends(octopoes_service),
    valid_time: datetime = Depends(extract_valid_time),
    types: set[type[OOI]] = Depends(extract_types),
    reference: Reference = Depends(extract_reference),
    depth: int = 1,
) -> ReferenceTree:
    return octopoes.get_ooi_tree(reference, valid_time, types, depth)


@router.get("/origins", tags=["Origins"])
def list_origins(
    octopoes: OctopoesService = Depends(octopoes_service),
    valid_time: datetime = Depends(extract_valid_time),
    offset: int = 0,
    limit: int | None = None,
    source: Reference | None = Query(None),
    result: Reference | None = Query(None),
    method: str | list[str] | None = Query(None),
    task_id: uuid.UUID | None = Query(None),
    origin_type: OriginType | None = Query(None),
) -> list[Origin]:
    return octopoes.origin_repository.list_origins(
        valid_time,
        task_id=task_id,
        offset=offset,
        limit=limit,
        source=source,
        result=result,
        method=method,
        origin_type=origin_type,
    )


@router.get("/origin_parameters", tags=["Origins"])
def list_origin_parameters(
    octopoes: OctopoesService = Depends(octopoes_service),
    valid_time: datetime = Depends(extract_valid_time),
    origin_id: set[str] = Query(default=set()),
) -> list[OriginParameter]:
    return octopoes.origin_parameter_repository.list_by_origin(origin_id, valid_time)


@router.post("/observations", tags=["Origins"])
def save_observation(observation: ValidatedObservation, octopoes: OctopoesService = Depends(octopoes_service)) -> None:
    origin = Origin(
        origin_type=OriginType.OBSERVATION,
        method=observation.method,
        source=observation.source,
        source_method=observation.source_method,
        result=[ooi.reference for ooi in observation.result],
        task_id=observation.task_id,
    )
    octopoes.save_origin(origin, observation.result, observation.valid_time)
    octopoes.commit()


@router.post("/declarations", tags=["Origins"])
def save_declaration(declaration: ValidatedDeclaration, octopoes: OctopoesService = Depends(octopoes_service)) -> None:
    origin = Origin(
        origin_type=OriginType.DECLARATION,
        method=declaration.method if declaration.method else "manual",
        source=declaration.ooi.reference,
        source_method=declaration.source_method,
        result=[declaration.ooi.reference],
        task_id=declaration.task_id if declaration.task_id else uuid.uuid4(),
    )
    octopoes.save_origin(origin, [declaration.ooi], declaration.valid_time, declaration.end_valid_time)
    octopoes.commit()


@router.post("/declarations/save_many", tags=["Origins"])
def save_many_declarations(
    declarations: list[ValidatedDeclaration], octopoes: OctopoesService = Depends(octopoes_service)
) -> None:
    for declaration in declarations:
        origin = Origin(
            origin_type=OriginType.DECLARATION,
            method=declaration.method if declaration.method else "manual",
            source=declaration.ooi.reference,
            source_method=declaration.source_method,
            result=[declaration.ooi.reference],
            task_id=declaration.task_id if declaration.task_id else uuid.uuid4(),
        )
        octopoes.save_origin(origin, [declaration.ooi], declaration.valid_time, declaration.end_valid_time)

    octopoes.commit()


@router.post("/affirmations", tags=["Origins"])
def save_affirmation(affirmation: ValidatedAffirmation, octopoes: OctopoesService = Depends(octopoes_service)) -> None:
    origin = Origin(
        origin_type=OriginType.AFFIRMATION,
        method=affirmation.method if affirmation.method else "hydration",
        source=affirmation.ooi.reference,
        source_method=affirmation.source_method,
        result=[affirmation.ooi.reference],
        task_id=affirmation.task_id if affirmation.task_id else uuid.uuid4(),
    )
    octopoes.save_origin(origin, [affirmation.ooi], affirmation.valid_time)
    octopoes.commit()


# ScanProfile-related endpoints
@router.get("/scan_profiles", tags=["Scan Profiles"])
def list_scan_profiles(
    octopoes: OctopoesService = Depends(octopoes_service),
    valid_time: datetime = Depends(extract_valid_time),
    scan_profile_type: str | None = Query(None),
) -> list[ScanProfileBase]:
    return octopoes.scan_profile_repository.list_scan_profiles(scan_profile_type, valid_time)


@router.put("/scan_profiles", tags=["Scan Profiles"])
def save_scan_profile(
    scan_profile: ScanProfile = Body(discriminator="scan_profile_type"),
    octopoes: OctopoesService = Depends(octopoes_service),
    valid_time: datetime = Depends(extract_valid_time),
) -> None:
    try:
        old_scan_profile = octopoes.scan_profile_repository.get(scan_profile.reference, valid_time)
    except ObjectNotFoundException:
        old_scan_profile = None

    octopoes.scan_profile_repository.save(old_scan_profile, scan_profile, valid_time)
    octopoes.commit()


@router.post("/scan_profiles/save_many", tags=["Scan Profiles"])
def save_many(
    scan_profiles: list[ScanProfile],
    octopoes: OctopoesService = Depends(octopoes_service),
    valid_time: datetime = Depends(extract_valid_time),
) -> None:
    for scan_profile in scan_profiles:
        try:
            old_scan_profile = octopoes.scan_profile_repository.get(scan_profile.reference, valid_time)
        except ObjectNotFoundException:
            old_scan_profile = None

        octopoes.scan_profile_repository.save(old_scan_profile, scan_profile, valid_time)

    octopoes.commit()


@router.get("/scan_profiles/recalculate", tags=["Scan Profiles"])
def recalculate_scan_profiles(
    octopoes: OctopoesService = Depends(octopoes_service), valid_time: datetime = Depends(extract_valid_time)
) -> None:
    octopoes.recalculate_scan_profiles(valid_time)
    octopoes.commit()


@router.get("/scan_profiles/inheritance", tags=["Scan Profiles"])
def get_scan_profile_inheritance(
    octopoes: OctopoesService = Depends(octopoes_service),
    valid_time: datetime = Depends(extract_valid_time),
    reference: Reference = Depends(extract_reference),
) -> list[InheritanceSection]:
    ooi = octopoes.get_ooi(reference, valid_time)
    if not ooi.scan_profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OOI does not have a scanprofile")

    start = InheritanceSection(
        reference=ooi.reference, level=ooi.scan_profile.level, scan_profile_type=ooi.scan_profile.scan_profile_type
    )
    if ooi.scan_profile.scan_profile_type == ScanProfileType.DECLARED.value:
        return [start]
    return octopoes.get_scan_profile_inheritance(reference, valid_time, [start])


@router.get("/findings", tags=["Findings"])
def list_findings(
    exclude_muted: bool = True,
    only_muted: bool = False,
    offset: int = DEFAULT_OFFSET,
    limit: int = DEFAULT_LIMIT,
    octopoes: OctopoesService = Depends(octopoes_service),
    valid_time: datetime = Depends(extract_valid_time),
    severities: set[RiskLevelSeverity] = Query(DEFAULT_SEVERITY_FILTER),
    search_string: str | None = None,
    order_by: Literal["score", "finding_type"] = "score",
    asc_desc: Literal["asc", "desc"] = "desc",
) -> Paginated[Finding]:
    return octopoes.ooi_repository.list_findings(
        severities, valid_time, exclude_muted, only_muted, offset, limit, search_string, order_by, asc_desc
    )


@router.get("/reports", tags=["Reports"])
def list_reports(
    offset: int = DEFAULT_OFFSET,
    limit: int = DEFAULT_LIMIT,
    octopoes: OctopoesService = Depends(octopoes_service),
    valid_time: datetime = Depends(extract_valid_time),
    recipe_id: uuid.UUID | None = Query(None),
) -> Paginated[HydratedReport]:
    return octopoes.ooi_repository.list_reports(valid_time, offset, limit, recipe_id)


@router.get("/reports/{report_id}", tags=["Reports"])
def get_report(
    report_id: str,
    octopoes: OctopoesService = Depends(octopoes_service),
    valid_time: datetime = Depends(extract_valid_time),
) -> HydratedReport:
    return octopoes.ooi_repository.get_report(valid_time, report_id)


@router.get("/findings/count_by_severity", tags=["Findings"])
def get_finding_type_count(
    octopoes: OctopoesService = Depends(octopoes_service), valid_time: datetime = Depends(extract_valid_time)
) -> Counter:
    return octopoes.ooi_repository.count_findings_by_severity(valid_time)


@router.post("/node", tags=["Node"])
def create_node(xtdb_session_: XTDBSession = Depends(xtdb_session)) -> None:
    try:
        xtdb_session_.client.create_node()
        xtdb_session_.commit()
    except XTDBException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Creating node failed") from e


@router.delete("/node", tags=["Node"])
def delete_node(xtdb_session_: XTDBSession = Depends(xtdb_session)) -> None:
    try:
        xtdb_session_.client.delete_node()
        xtdb_session_.commit()
    except XTDBException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Deleting node failed") from e


@router.post("/bits/recalculate", tags=["Bits"])
def recalculate_bits(octopoes: OctopoesService = Depends(octopoes_service)) -> int:
    try:
        inference_count = octopoes.recalculate_bits()
    except ObjectNotFoundException:
        logger.exception("Failed to recalculate bits")
        raise

    octopoes.commit()

    return inference_count


@router.get("/io/export", tags=["io"])
def exporter(xtdb_session_: XTDBSession = Depends(xtdb_session)) -> Any:
    return xtdb_session_.client.export_transactions()


@sync_to_async
def importer(data: bytes, xtdb_session_: XTDBSession, reset: bool = False) -> dict[str, int]:
    try:
        ops: list[dict[str, Any]] = list(map(itemgetter("txOps"), json.loads(data)))
    except Exception as e:
        logger.debug("Error parsing objects", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error parsing objects") from e
    if reset:
        try:
            xtdb_session_.client.delete_node()
            xtdb_session_.client.create_node()
            xtdb_session_.commit()
        except XTDBException as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error recreating nodes"
            ) from e
    for op in ops:
        try:
            operations: list[Operation] = [
                (OperationType(x[0]), x[1], datetime.strptime(x[2], "%Y-%m-%dT%H:%M:%SZ")) for x in op
            ]
            xtdb_session_.client.submit_transaction(operations)
        except Exception as e:
            logger.debug("Error importing objects", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error importing object {op}"
            ) from e
    return {"detail": len(ops)}


@router.post("/io/import/add", tags=["io"])
async def importer_add(request: Request, xtdb_session_: XTDBSession = Depends(xtdb_session)) -> dict[str, int]:
    try:
        data = await request.body()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error receiving objects") from e
    return await importer(data, xtdb_session_)


@router.post("/io/import/new", tags=["io"])
async def importer_new(request: Request, xtdb_session_: XTDBSession = Depends(xtdb_session)) -> dict[str, int]:
    try:
        data = await request.body()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error receiving objects") from e
    return await importer(data, xtdb_session_, True)


@router.post("/origins/migrate", tags=["Origins"])
def migrate_origins(
    origins: list[Origin],
    session: XTDBSession = Depends(xtdb_session),
    valid_time: datetime = Depends(extract_valid_time),
) -> None:
    for origin in origins:
        if origin.source_method is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Only origins with a new source method can be migrated"
            )

        session.add((OperationType.PUT, XTDBOriginRepository.serialize(origin), valid_time))

        origin.source_method = None  # To ensure the id property has the original pk value that we want to delete
        session.add((OperationType.DELETE, origin.id, valid_time))

    session.commit()  # The save-delete order is important to avoid garbage collection of the results


@router.get("/nibbles", tags=["nibbles"])
def nibbles_list(octopoes: OctopoesService = Depends(octopoes_service)) -> list[str]:
    return octopoes.nibbler.list_nibbles()


@router.get("/nibbles/status", tags=["nibbles"])
def nibbles_list_enabled(enabled: bool = True, octopoes: OctopoesService = Depends(octopoes_service)) -> list[str]:
    return [nibble.id for nibble in octopoes.nibbler.nibbles.values() if nibble.enabled == enabled]


@router.get("/nibbles/update", tags=["nibbles"])
def nibbles_update(
    valid_time: datetime = Depends(extract_valid_time), octopoes: OctopoesService = Depends(octopoes_service)
) -> list[str]:
    octopoes.nibbler.update_nibbles(valid_time)
    return octopoes.nibbler.list_nibbles()


@router.get("/nibbles/disable", tags=["nibbles"])
def nibbles_disable(octopoes: OctopoesService = Depends(octopoes_service)) -> list[str]:
    if octopoes.nibbler.federated:
        octopoes.nibbler.toggle_nibbles(list(octopoes.nibbler.nibbles.keys()), False, datetime.now())
    octopoes.nibbler.disable()
    return nibbles_list(octopoes)


@router.get("/nibbles/available", tags=["nibbles"])
def nibbles_available(octopoes: OctopoesService = Depends(octopoes_service)) -> list[str]:
    return octopoes.nibbler.list_available_nibbles()


@router.get("/nibbles/select", tags=["nibbles"])
def nibbles_toggle(
    state: bool, nibble_ids: list[str] = Query(), octopoes: OctopoesService = Depends(octopoes_service)
) -> list[str]:
    octopoes.nibbler.toggle_nibbles(nibble_ids, state, datetime.now())
    return octopoes.nibbler.list_nibbles()


@router.get("/nibbles/checksum", tags=["nibbles"])
def nibbles_checksum(octopoes: OctopoesService = Depends(octopoes_service)) -> dict[str, str | None]:
    return {nibble.id: nibble._checksum for nibble in octopoes.nibbler.nibbles.values()}


@router.get("/nibbles/federate", tags=["nibbles"])
def nibbles_federate(octopoes: OctopoesService = Depends(octopoes_service)):
    octopoes.nibbler.federated = True


@router.get("/nibbles/register", tags=["nibbles"])
def nibbles_register(octopoes: OctopoesService = Depends(octopoes_service)):
    octopoes.nibbler.register(datetime.now())


@router.get("/nibbles/retrieve", tags=["nibbles"])
def nibble_retrieve(
    nibble_ids: list[str] | None = Query(None),
    valid_time: datetime = Depends(extract_valid_time),
    octopoes: OctopoesService = Depends(octopoes_service),
) -> dict[str, list[list[Any]]]:
    return octopoes.nibbler.retrieve(nibble_ids, valid_time)


@router.get("/nibbles/yields", tags=["nibbles"])
def nibble_yields(
    nibble_ids: list[str] | None = Query(None),
    valid_time: datetime = Depends(extract_valid_time),
    octopoes: OctopoesService = Depends(octopoes_service),
) -> dict[str, dict[tuple[Reference | None, ...], list[Reference]]]:
    return octopoes.nibbler.yields(nibble_ids, valid_time)
