#!/usr/bin/env python3

"""Migration script for v1.17.0 due to a bug in the garbage collection. To be removed in later versions.
https://github.com/minvws/nl-kat-coordination/issues/2875"""

import json
import logging.config
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
from httpx import HTTPStatusError
from sqlalchemy.orm import sessionmaker

from boefjes.api import get_bytes_client
from boefjes.clients.scheduler_client import get_octopoes_api_connector
from boefjes.config import settings
from boefjes.dependencies.plugins import PluginService
from boefjes.sql.config_storage import create_config_storage
from boefjes.sql.db import get_engine
from boefjes.sql.organisation_storage import create_organisation_storage
from boefjes.sql.plugin_storage import create_plugin_storage
from boefjes.storage.interfaces import OrganisationStorage
from boefjes.worker.models import Boefje
from boefjes.worker.repository import get_local_repository
from octopoes.models.origin import OriginType

sys.path.append(str(Path(__file__).resolve().parent.parent))


with settings.log_cfg.open() as f:
    logging.config.dictConfig(json.load(f))

logger = logging.getLogger(__name__)


def upgrade(organisation_repository: OrganisationStorage, valid_time: datetime | None = None) -> tuple[int, int]:
    """
    Perform the migration for all organisations in the database. The happy flow in this script is idempotent,
    meaning that it can be rerun until there are no, or only expected, exceptions.
    """
    if valid_time is None:
        valid_time = datetime.now(timezone.utc)

    bytes_client = get_bytes_client()
    bytes_client.login()

    total_failed = 0
    total_processed = 0

    organisations = organisation_repository.get_all()
    logger.info("Processing %s organisations in total", len(organisations))

    boefjes_per_normalizer = collect_boefjes_per_normalizer()
    logger.info("Found %s normalizers", len(boefjes_per_normalizer))

    for organisation_id in organisations:
        connector = get_octopoes_api_connector(organisation_id)
        logger.info("Processing organisation [organization_id=%s]", organisation_id)

        failed, processed = migrate_organisation(
            bytes_client, connector, organisation_id, boefjes_per_normalizer, valid_time
        )
        total_failed += failed
        total_processed += processed

        logger.info("Processed organisation [total_processed=%s, total_failed=%s]", processed, failed)

    logger.info("Finished migration [total_processed=%s, total_failed=%s]", total_processed, total_failed)

    return total_processed, total_failed


def migrate_organisation(
    bytes_client, connector, organisation_id, boefjes_per_normalizer, valid_time
) -> tuple[int, int]:
    """
    For each organisation, we paginate through the origin API, find the matching normalizer meta in Bytes,
    and set the source_method to the boefje id. Then update the origin, i.e. save it and delete the old one.
    """

    try:
        connector.health()
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.warning(
                "Organisation found that does not exist in Octopoes [organisation_id=%s]. Make sure to remove this "
                "organisation from the Katalogus database if it is no longer in use.",
                organisation_id,
            )
        raise

    failed = 0
    processed = 0

    offset = 0
    page_size = 200

    bulk_updated_origins = []

    while True:
        # We loop through the paginated API until we reach the end

        origins = connector.list_origins(
            valid_time, method=[x for x in boefjes_per_normalizer], offset=offset, limit=page_size
        )
        logger.info("Processing %s origins", len(origins))

        for origin in origins:
            if origin.source_method is not None or origin.origin_type == OriginType.INFERENCE:
                continue

            if origin.method in boefjes_per_normalizer and len(boefjes_per_normalizer[origin.method]) == 1:
                origin.source_method = boefjes_per_normalizer[origin.method][0].id
                bulk_updated_origins.append(origin)
                continue

            try:
                normalizer_meta = bytes_client.get_normalizer_meta(origin.task_id)
                origin.source_method = normalizer_meta.raw_data.boefje_meta.boefje.id
                bulk_updated_origins.append(origin)
            except HTTPStatusError as error:
                # We expect to find Declaration/Affirmations without a normalizer meta
                if error.response.status_code == 404 and origin.method != "manual":
                    logger.warning(
                        "Could not find normalizer_meta [task_id=%s, method=%s, origin_type=%s]",
                        origin.task_id,
                        origin.method,
                        origin.origin_type,
                    )
                elif error.response.status_code == 404:
                    logger.info(
                        "Could not find normalizer_meta [task_id=%s, method=%s, origin_type=%s]",
                        origin.task_id,
                        origin.method,
                        origin.origin_type,
                    )
                else:
                    logger.exception(
                        "Could not find normalizer_meta [task_id=%s, method=%s, origin_type=%s]",
                        origin.task_id,
                        origin.method,
                        origin.origin_type,
                    )
                    failed += 1

                continue

        if len(origins) < 200:
            logger.info("Processed all origins [organization_id=%s]", organisation_id)
            break

        offset += page_size

    connector._bulk_migrate_origins(bulk_updated_origins, valid_time)
    processed += len(bulk_updated_origins)

    return failed, processed


def collect_boefjes_per_normalizer() -> dict[str, list[Boefje]]:
    session = sessionmaker(bind=get_engine())()

    all_plugins = PluginService(
        create_plugin_storage(session), create_config_storage(session), get_local_repository()
    )._get_all_without_enabled()

    normalizers = {}

    for normalizer in [x for x in all_plugins.values() if x.type == "normalizer"]:
        boefjes = []

        for plugin in all_plugins.values():
            if plugin.type == "boefje" and f"boefje/{plugin.id}" in normalizer.consumes:
                boefjes.append(plugin)

        normalizers[normalizer.id] = boefjes

    session.close()

    return normalizers


@click.command()
def main():
    session = sessionmaker(bind=get_engine())()
    organisations = create_organisation_storage(session)

    upgrade(organisations)

    session.close()


if __name__ == "__main__":
    main()
