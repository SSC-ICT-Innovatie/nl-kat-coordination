import structlog
from cachetools import TTLCache, cached
from prometheus_client import CollectorRegistry, Gauge

from bytes.config import get_settings
from bytes.repositories.meta_repository import MetaDataRepository

collector_registry = CollectorRegistry()


bytes_database_organizations_total = Gauge(
    name="bytes_database_organizations_total",
    documentation="Total amount of organizations in the bytes database.",
    registry=collector_registry,
)
bytes_database_raw_files_total = Gauge(
    name="bytes_database_raw_files_total",
    documentation="Total amount of raw files in the bytes database.",
    registry=collector_registry,
    labelnames=["organization_id"],
)

logger = structlog.get_logger(__name__)


def ignore_arguments_key(meta_repository: MetaDataRepository) -> str:
    return ""


@cached(cache=TTLCache(maxsize=1, ttl=get_settings().metrics_ttl_seconds), key=ignore_arguments_key)
def cached_counts_per_organization(meta_repository: MetaDataRepository) -> dict[str, int]:
    logger.debug(
        "Metrics cache miss for cached_counts_per_organization, ttl set to %s seconds",
        get_settings().metrics_ttl_seconds,
    )

    return meta_repository.get_raw_file_count_per_organization()


def get_registry(meta_repository: MetaDataRepository) -> CollectorRegistry:
    counts_per_organization = cached_counts_per_organization(meta_repository)
    bytes_database_organizations_total.set(len(counts_per_organization))

    for organization_id, count in counts_per_organization.items():
        bytes_database_raw_files_total.labels(organization_id).set(count)

    return collector_registry
