import time
import timeit
from datetime import datetime, timezone
from logging import config
from pathlib import Path

import structlog
import yaml
from httpx import HTTPError

from octopoes.config.settings import Settings
from octopoes.connector.katalogus import KATalogusClient
from octopoes.core.app import get_octopoes

settings = Settings()
logger = structlog.get_logger(__name__)

try:
    with Path(settings.log_cfg).open() as log_config:
        config.dictConfig(yaml.safe_load(log_config))
        logger.info("Configured loggers with config: %s", settings.log_cfg)
except FileNotFoundError:
    logger.warning("No log config found at: %s", settings.log_cfg)

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper("iso", utc=False),
        (
            structlog.dev.ConsoleRenderer(colors=True, pad_level=False)
            if settings.logging_format == "text"
            else structlog.processors.JSONRenderer()
        ),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


def scan_profile_recalculations(katalogusclient: KATalogusClient, octopii: dict) -> None:
    try:
        orgs = katalogusclient.get_organisations()
    except HTTPError:
        logger.exception("Failed getting organizations from KATalogus")
        raise
    for org in orgs:
        if org not in octopii:
            octopii[org] = {"octopoes": get_octopoes(org), "last_transaction": 0, "org": org}
        last_transaction = recalculate_scan_profiles_for_org(octopii[org])
        if last_transaction:
            # there's a possible race condition in here, where we dont
            # notice updates unrelated to our scan_profiles change,
            # ideally we'd trigger another loop in 60s because of those,
            # but since we have no database lock we assume we are the only one
            # writing transactions during our scan_profile calculation
            # if not, they will be picked up with the next batch of changes
            # anyway.
            octopii[org]["last_transaction"] = last_transaction


def recalculate_scan_profiles_for_org(recalc_org: dict) -> int | None:
    timer = timeit.default_timer()
    max_id = recalc_org["octopoes"].session.client.latest_completed_tx()
    if max_id and recalc_org["last_transaction"] == max_id["txId"]:
        logger.debug(
            "skipping scan profile recalculation task, no new transactions present, last transaction: %i [org=%s]",
            max_id["txId"],
            recalc_org["org"],
        )
        return None
    elif max_id:
        logger.debug(
            "Most recent worked transactions %i, most recent %i [org=%s]",
            recalc_org["last_transaction"],
            max_id["txId"],
            recalc_org["org"],
        )

    try:
        recalc_org["octopoes"].recalculate_scan_profiles(datetime.now(timezone.utc))
        transactions = recalc_org["octopoes"].session.commit()
        duration = timeit.default_timer() - timer
        max_id = recalc_org["octopoes"].session.client.latest_completed_tx()
        if max_id:
            # return the max_id after this update. So we dont trigger a likely empty loop
            # just because we changed some scanprofiles this loop.
            logger.info(
                """Finished scan profile recalculation on %i unproccessed transactions,
                with resulting transactioncount: %i [org=%s] [dur=%.2fs]""",
                (max_id["txId"] - recalc_org["last_transaction"]),
                transactions,
                recalc_org["org"],
                duration,
            )
            return max_id["txId"]
        else:
            # last_transaction should always increment,
            # but None is technically a possible return value
            return 0
    except Exception:
        logger.exception(
            "Failed recalculating scan profiles [org=%s] [dur=%.2fs]", recalc_org["org"], timeit.default_timer() - timer
        )
    return None


def main():
    logger.info("Scan profile recalculation process started.")
    katalogusclient = KATalogusClient(str(settings.katalogus_api))
    octopii: dict[str, dict] = {}
    while True:
        scan_profile_recalculations(katalogusclient, octopii)
        time.sleep(settings.scan_level_recalculation_interval)


if __name__ == "__main__":
    main()
