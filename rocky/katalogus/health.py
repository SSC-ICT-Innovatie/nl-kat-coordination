import structlog
from httpx import HTTPError

from katalogus.client import get_katalogus_client
from rocky.health import ServiceHealth

logger = structlog.get_logger(__name__)


def get_katalogus_health() -> ServiceHealth:
    try:
        katalogus_client = get_katalogus_client()  # For the health endpoint the organization has no effect
        katalogus_health = katalogus_client.health()
    except HTTPError:
        logger.exception("Error while retrieving KATalogus health state")
        katalogus_health = ServiceHealth(
            service="katalogus", healthy=False, additional="Could not connect to KATalogus. Service is possibly down"
        )
    return katalogus_health
