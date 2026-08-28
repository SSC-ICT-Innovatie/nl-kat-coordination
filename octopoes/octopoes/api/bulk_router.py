import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, Query

from octopoes.api.router import extract_reference, extract_valid_time, settings
from octopoes.api.router import settings as extract_settings
from octopoes.config.settings import QUEUE_NAME_OCTOPOES, Settings
from octopoes.core.app import bootstrap_octopoes, get_xtdb_client
from octopoes.events.manager import EventManager
from octopoes.models import Reference
from octopoes.models.exception import ObjectNotFoundException
from octopoes.models.ooi.reports import HydratedReport
from octopoes.models.types import OOIType
from octopoes.repositories.ooi_repository import XTDBOOIRepository
from octopoes.tasks.app import app as celery_app
from octopoes.xtdb.client import XTDBSession

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/reports", tags=["Reports"])
def list_reports(
    reports_filters: list[tuple[str, uuid.UUID]],
    settings_: Settings = Depends(extract_settings),
    valid_time: datetime = Depends(extract_valid_time),
) -> dict[uuid.UUID, HydratedReport]:
    """
    An efficient endpoint for getting reports across organizations
    """

    # The reason for creating the event_manager do this in the loop is the '_try_connect()' call in the __init__
    # possibly slowing this down, while this API was introduced to improve performance. Simply reusing it for all
    # clients works because the event manager is only used in callbacks triggered on a `commit()`, while these queries
    # are read-only and hence don't need a `commit()` as no events would be triggered. (A cleaner solution would perhaps
    #  be to extract an interface and pass a new NullManager.)
    event_manager = EventManager("null", str(settings_.queue_uri), celery_app, QUEUE_NAME_OCTOPOES)

    # The xtdb_http_client is also created outside the loop and the `_client` property changed inside the loop instead,
    # to reuse the httpx Session for all requests.
    xtdb_http_client = get_xtdb_client(str(settings_.xtdb_uri), "")
    ooi_repository = XTDBOOIRepository(event_manager, XTDBSession(xtdb_http_client))

    reports = {}

    for client, recipe_id in reports_filters:
        xtdb_http_client.client = client

        for report in ooi_repository.list_reports(valid_time, 0, 1, recipe_id, ignore_count=True).items:
            reports[recipe_id] = report

    return reports


@router.get("/object-clients", tags=["Objects"])
def list_object_clients(
    clients: set[str] = Query(default_factory=set),
    reference: Reference = Depends(extract_reference),
    settings_: Settings = Depends(settings),
    valid_time: datetime = Depends(extract_valid_time),
) -> dict[str, OOIType]:
    """
    An efficient endpoint for checking if OOIs live in multiple organizations
    """

    # See list_reports() for some of the reasoning behind the below code
    xtdb_http_client = get_xtdb_client(str(settings_.xtdb_uri), "")
    session = XTDBSession(xtdb_http_client)

    octopoes = bootstrap_octopoes(settings_, "null", session)
    clients_with_reference = {}

    for client in clients:
        xtdb_http_client.client = client

        try:
            ooi = octopoes.get_ooi(reference, valid_time)
        except ObjectNotFoundException:
            continue

        clients_with_reference[client] = ooi

    return clients_with_reference
