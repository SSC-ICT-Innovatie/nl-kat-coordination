#!/usr/bin/env python3
# ruff: noqa: E402

import logging
import pdb
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import click
from sqlalchemy.orm import sessionmaker

from boefjes.clients.scheduler_client import SchedulerAPIClient
from boefjes.dependencies.plugins import PluginService
from boefjes.sql.config_storage import create_config_storage
from boefjes.sql.db import get_engine
from boefjes.sql.plugin_storage import create_plugin_storage
from boefjes.worker.boefje_handler import LocalBoefjeHandler

sys.path.append(str(Path(__file__).resolve().parent.parent))

from boefjes.job_handler import bytes_api_client
from boefjes.worker.interfaces import Task, TaskStatus
from boefjes.worker.job_models import Boefje, BoefjeMeta
from boefjes.worker.repository import get_local_repository

logging.basicConfig(stream=sys.stdout, level=logging.INFO, force=True)


@click.command()
@click.option("--pdb", "start_pdb", is_flag=True, help="Start pdb on exceptions")
@click.argument("organization_code")
@click.argument("boefje_id")
@click.argument("input_ooi")
def run_boefje(start_pdb, organization_code, boefje_id, input_ooi):
    """Run boefje"""

    meta = BoefjeMeta(id=uuid.uuid4(), boefje=Boefje(id=boefje_id), organization=organization_code, input_ooi=input_ooi)

    local_repository = get_local_repository()

    session = sessionmaker(bind=get_engine())()
    plugin_service = PluginService(create_plugin_storage(session), create_config_storage(session), local_repository)
    meta = SchedulerAPIClient(plugin_service, "/dev/null")._hydrate_boefje_meta(meta)

    handler = LocalBoefjeHandler(local_repository, bytes_api_client)
    task = Task(
        id=meta.id,
        scheduler_id="manual",
        schedule_id=None,
        organisation=organization_code,
        priority=1,
        status=TaskStatus.RUNNING,
        type="boefje",
        data=meta,
        created_at=meta.started_at or datetime.now(timezone.utc),
        modified_at=meta.started_at or datetime.now(timezone.utc),
    )
    try:
        result = handler.handle(task)
        if result and result[1].files:
            logging.info("Raw file IDs: %s", ", ".join(f.name for f in result[1].files))
    except Exception:
        if start_pdb:
            pdb.post_mortem()

        raise


if __name__ == "__main__":
    run_boefje()
