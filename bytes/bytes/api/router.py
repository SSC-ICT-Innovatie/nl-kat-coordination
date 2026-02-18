from base64 import b64decode, b64encode
from uuid import UUID

import structlog
from cachetools import TTLCache, cached
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from httpx import codes
from starlette.responses import JSONResponse

from bytes.api.models import BoefjeOutput, File, StatusEnum
from bytes.auth import authenticate_token
from bytes.config import get_settings
from bytes.database.sql_meta_repository import MetaIntegrityError, ObjectNotFoundException, create_meta_data_repository
from bytes.events.events import RawFileReceived
from bytes.events.manager import EventManager
from bytes.models import BoefjeMeta, MimeType, NormalizerMeta, RawData, RawDataMeta
from bytes.rabbitmq import create_event_manager
from bytes.repositories.meta_repository import BoefjeMetaFilter, MetaDataRepository, NormalizerMetaFilter, RawDataFilter

logger = structlog.get_logger(__name__)
router = APIRouter(dependencies=[Depends(authenticate_token)])
BOEFJE_META_TAG = "BoefjeMeta"
NORMALIZER_META_TAG = "NormalizerMeta"
RAW_TAG = "Raw"


@router.post("/boefje_meta", tags=[BOEFJE_META_TAG])
def create_boefje_meta(
    boefje_meta: BoefjeMeta, meta_repository: MetaDataRepository = Depends(create_meta_data_repository)
) -> JSONResponse:
    try:
        with meta_repository:
            meta_repository.save_boefje_meta(boefje_meta)
    except MetaIntegrityError:
        return JSONResponse(
            {"status": "failed", "message": "Integrity error: object might already exist"},
            status_code=codes.BAD_REQUEST,
        )

    return JSONResponse({"status": "success"}, status_code=codes.CREATED)


@router.get("/boefje_meta/{boefje_meta_id}", response_model=BoefjeMeta, tags=[BOEFJE_META_TAG])
def get_boefje_meta_by_id(
    boefje_meta_id: UUID, meta_repository: MetaDataRepository = Depends(create_meta_data_repository)
) -> BoefjeMeta:
    with meta_repository:
        try:
            meta = meta_repository.get_boefje_meta_by_id(boefje_meta_id)
        except ObjectNotFoundException as error:
            raise HTTPException(status_code=codes.NOT_FOUND, detail="Boefje meta not found") from error

        logger.debug("Found meta: %s", meta)

        return meta


@router.get("/boefje_meta", response_model=list[BoefjeMeta], tags=[BOEFJE_META_TAG])
def get_boefje_meta(
    organization: str,
    boefje_id: str | None = None,
    input_ooi: str | None = None,
    limit: int = 1,
    offset: int = 0,
    descending: bool = True,
    meta_repository: MetaDataRepository = Depends(create_meta_data_repository),
) -> list[BoefjeMeta]:
    logger.debug(
        "Filtering boefje_meta on: boefje_id=%s, input_ooi=%s, limit=%s, descending=%s",
        boefje_id,
        input_ooi,
        limit,
        descending,
    )
    query_filter = BoefjeMetaFilter(
        organization=organization,
        boefje_id=boefje_id,
        input_ooi=input_ooi,
        limit=limit,
        offset=offset,
        descending=descending,
    )

    with meta_repository:
        boefje_meta_list = meta_repository.get_boefje_meta(query_filter)

    logger.debug("Found %s boefje meta entries", len(boefje_meta_list))
    return boefje_meta_list


@router.post("/normalizer_meta", tags=[NORMALIZER_META_TAG])
def create_normalizer_meta(
    normalizer_meta: NormalizerMeta, meta_repository: MetaDataRepository = Depends(create_meta_data_repository)
) -> JSONResponse:
    try:
        with meta_repository:
            meta_repository.save_normalizer_meta(normalizer_meta)
    except MetaIntegrityError:
        return JSONResponse(
            {"status": "failed", "message": "Integrity error: object might already exist"},
            status_code=codes.BAD_REQUEST,
        )

    return JSONResponse({"status": "success"}, status_code=codes.CREATED)


@router.get("/normalizer_meta/{normalizer_meta_id}", response_model=NormalizerMeta, tags=[NORMALIZER_META_TAG])
def get_normalizer_meta_by_id(
    normalizer_meta_id: UUID, meta_repository: MetaDataRepository = Depends(create_meta_data_repository)
) -> NormalizerMeta:
    try:
        return meta_repository.get_normalizer_meta_by_id(normalizer_meta_id)
    except ObjectNotFoundException as error:
        raise HTTPException(status_code=codes.NOT_FOUND, detail="Normalizer meta not found") from error


@router.get("/normalizer_meta", response_model=list[NormalizerMeta], tags=[NORMALIZER_META_TAG])
def get_normalizer_meta(
    organization: str,
    normalizer_id: str | None = None,
    raw_id: UUID | None = None,
    limit: int = 1,
    offset: int = 0,
    descending: bool = True,
    meta_repository: MetaDataRepository = Depends(create_meta_data_repository),
) -> list[NormalizerMeta]:
    logger.debug(
        "Filtering normalizer_meta on: normalizer_id=%s, raw_id=%s, limit=%s, offset=%s, descending=%s",
        normalizer_id,
        raw_id,
        limit,
        offset,
        descending,
    )
    query_filter = NormalizerMetaFilter(
        organization=organization,
        normalizer_id=normalizer_id,
        raw_id=raw_id,
        limit=limit,
        offset=offset,
        descending=descending,
    )

    with meta_repository:
        normalizer_meta_list = meta_repository.get_normalizer_meta(query_filter)

    logger.debug("Found %s normalizer meta entries", len(normalizer_meta_list))
    return normalizer_meta_list


@router.post("/raw", tags=[RAW_TAG])
def create_raw(
    boefje_meta_id: UUID,
    boefje_output: BoefjeOutput,
    meta_repository: MetaDataRepository = Depends(create_meta_data_repository),
    event_manager: EventManager = Depends(create_event_manager),
) -> dict[str, UUID]:
    """Parse all the raw files from the request and return the ids. The ids are ordered according to the order from the
    request data, but we assume the `name` field is unique, and hence return a mapping of the file name to the id."""

    raw_ids = {}
    mime_types_by_id = {
        raw.id: set(raw.mime_types) for raw in meta_repository.get_raw(RawDataFilter(boefje_meta_id=boefje_meta_id))
    }
    all_parsed_mime_types = list(mime_types_by_id.values())

    for raw in boefje_output.files:
        parsed_mime_types = {MimeType(value=x) for x in raw.tags}

        if parsed_mime_types in mime_types_by_id.values():
            # Set the id for this file using the precomputed dict that maps existing primary keys to the mime-type set.
            # We do this since a boefje_meta should have unique raw files based on the mime-types, so this deduplicates.
            raw_ids[raw.name] = list(mime_types_by_id.keys())[list(mime_types_by_id.values()).index(parsed_mime_types)]

            continue

        if parsed_mime_types in all_parsed_mime_types:
            raise HTTPException(
                status_code=codes.BAD_REQUEST, detail="Content types do not define unique sets of mime types."
            )

        try:
            meta = meta_repository.get_boefje_meta_by_id(boefje_meta_id)
            raw_data = RawData(value=b64decode(raw.content.encode()), boefje_meta=meta, mime_types=parsed_mime_types)

            with meta_repository:
                raw_id = meta_repository.save_raw(raw_data)
                raw_ids[raw.name] = raw_id

            all_parsed_mime_types.append(parsed_mime_types)

            event = RawFileReceived(
                organization=meta.organization,
                raw_data=RawDataMeta(id=raw_id, boefje_meta=raw_data.boefje_meta, mime_types=raw_data.mime_types),
            )
            event_manager.publish(event)
        except Exception as error:
            logger.exception("Error saving raw data")
            raise HTTPException(status_code=codes.INTERNAL_SERVER_ERROR, detail="Could not save raw data") from error

        all_parsed_mime_types.append(parsed_mime_types)

    return raw_ids


@router.get("/raw/{raw_id}", tags=[RAW_TAG])
def get_raw_by_id(raw_id: UUID, meta_repository: MetaDataRepository = Depends(create_meta_data_repository)) -> Response:
    try:
        raw_data = meta_repository.get_raw_by_id(raw_id)
    except ObjectNotFoundException as error:
        raise HTTPException(status_code=codes.NOT_FOUND, detail="No raw data found") from error

    return Response(raw_data.value, media_type="application/octet-stream")


@router.get("/raw/{raw_id}/meta", tags=[RAW_TAG])
def get_raw_meta_by_id(
    raw_id: UUID, meta_repository: MetaDataRepository = Depends(create_meta_data_repository)
) -> RawDataMeta:
    try:
        raw_meta = meta_repository.get_raw_meta_by_id(raw_id)
    except ObjectNotFoundException as error:
        raise HTTPException(status_code=codes.NOT_FOUND, detail="No raw data found") from error

    return raw_meta


@router.get("/raw", response_model=list[RawDataMeta], tags=[RAW_TAG])
def get_raw(
    organization: list[str] | None = None,
    boefje_meta_id: UUID | None = None,
    normalized: bool | None = None,
    raw_ids: list[UUID] | None = Query(None),
    limit: int = 1,
    mime_types: list[str] | None = Query(None),
    meta_repository: MetaDataRepository = Depends(create_meta_data_repository),
) -> list[RawDataMeta]:
    """Get a filtered list of RawDataMeta objects, which contains metadata of a RawData object without the contents"""

    parsed_mime_types = [] if mime_types is None else [MimeType(value=mime_type) for mime_type in mime_types]

    query_filter = RawDataFilter(
        organization=organization,
        boefje_meta_id=boefje_meta_id,
        raw_ids=raw_ids,
        normalized=normalized,
        mime_types=parsed_mime_types,
        limit=limit,
    )

    return meta_repository.get_raw(query_filter)


@router.get("/raws", response_model=BoefjeOutput, tags=[RAW_TAG])
def get_raws(
    organization: list[str] | None = Query(None),
    boefje_meta_id: UUID | None = None,
    raw_ids: list[UUID] | None = Query(None),
    normalized: bool | None = None,
    limit: int = 1,
    mime_types: list[str] | None = Query(None),
    meta_repository: MetaDataRepository = Depends(create_meta_data_repository),
) -> BoefjeOutput:
    """Get a filtered list of RawData"""

    parsed_mime_types = [] if mime_types is None else [MimeType(value=mime_type) for mime_type in mime_types]

    query_filter = RawDataFilter(
        organization=organization,
        boefje_meta_id=boefje_meta_id,
        raw_ids=raw_ids,
        normalized=normalized,
        mime_types=parsed_mime_types,
        limit=limit,
    )

    raws = meta_repository.get_raws(query_filter)
    status = StatusEnum.COMPLETED

    if len(raws) == 1 and {"error/boefje"} in raws[0][1].mime_types:
        status = StatusEnum.FAILED

    return BoefjeOutput(
        status=status,
        files=[
            File(name=str(raw_id), content=b64encode(raw.value).decode(), tags=[m.value for m in raw.mime_types])
            for raw_id, raw in raws
        ],
    )


@router.get("/mime_types", response_model=dict[str, int], tags=[RAW_TAG])
def get_raw_count_per_mime_type(
    organization: list[str] | None = None,
    boefje_meta_id: UUID | None = None,
    normalized: bool | None = None,
    mime_types: list[str] | None = Query(None),
    meta_repository: MetaDataRepository = Depends(create_meta_data_repository),
) -> dict[str, int]:
    parsed_mime_types = [] if mime_types is None else [MimeType(value=mime_type) for mime_type in mime_types]

    query_filter = RawDataFilter(
        organization=organization,
        boefje_meta_id=boefje_meta_id,
        normalized=normalized,
        mime_types=parsed_mime_types,
        offset=None,
        limit=None,
    )

    return cached_counts_per_mime_type(meta_repository, query_filter)


def ignore_arguments_key(meta_repository: MetaDataRepository, query_filter: RawDataFilter) -> str:
    """Helper to not cache based on the stateful meta_repository, but only use the query parameters as a key."""
    return query_filter.model_dump_json()


@cached(
    cache=TTLCache(maxsize=get_settings().metrics_cache_size, ttl=get_settings().metrics_ttl_seconds),
    key=ignore_arguments_key,
)
def cached_counts_per_mime_type(meta_repository: MetaDataRepository, query_filter: RawDataFilter) -> dict[str, int]:
    logger.debug(
        "Metrics cache miss for cached_counts_per_mime_type, ttl set to %s seconds", get_settings().metrics_ttl_seconds
    )

    return meta_repository.get_raw_file_count_per_mime_type(query_filter)
