import structlog
from fastapi import APIRouter, Depends

from boefjes.config import settings
from boefjes.dependencies.plugins import get_pagination_parameters
from boefjes.sql.config_storage import get_config_storage
from boefjes.storage.interfaces import ConfigStorage
from boefjes.worker.models import BoefjeConfig, PaginationParameters

router = APIRouter(tags=["configs"])

logger = structlog.get_logger(__name__)


@router.get("/configs", response_model=list[BoefjeConfig])
def list_configs(
    organisation_id: str | None = None,
    boefje_id: str | None = None,
    enabled: bool | None = None,
    with_duplicates: bool = False,
    pagination_params: PaginationParameters = Depends(get_pagination_parameters),
    config_storage: ConfigStorage = Depends(get_config_storage),
) -> list[BoefjeConfig]:
    if not settings.deduplicate:
        with_duplicates = False

    with config_storage as store:
        configs = store.list_boefje_configs(
            pagination_params.offset, pagination_params.limit, organisation_id, boefje_id, enabled, with_duplicates
        )

    return configs
