#!/usr/bin/env python3
# ruff: noqa: E402

import logging
import pdb
import sys
import uuid
from pathlib import Path

import click

sys.path.append(str(Path(__file__).resolve().parent.parent))

from boefjes.config import settings
from boefjes.job_handler import NormalizerHandler, bytes_api_client
from boefjes.local.runner import LocalNormalizerJobRunner
from boefjes.worker.job_models import Normalizer, NormalizerMeta
from boefjes.worker.repository import get_local_repository

logging.basicConfig(stream=sys.stdout, level=logging.INFO, force=True)


@click.command()
@click.option("--pdb", "start_pdb", is_flag=True, help="Start pdb on exceptions")
@click.argument("normalizer_id")
@click.argument("raw_id")
def run_normalizer(start_pdb, normalizer_id, raw_id):
    """Run normalizer"""

    bytes_api_client.login()
    raw = bytes_api_client.get_raw_meta(raw_id)

    meta = NormalizerMeta(id=uuid.uuid4(), raw_data=raw, normalizer=Normalizer(id=normalizer_id))

    local_repository = get_local_repository()

    handler = NormalizerHandler(
        LocalNormalizerJobRunner(local_repository), bytes_api_client, settings.scan_profile_whitelist
    )
    try:
        handler.handle(meta)
    except Exception:
        if start_pdb:
            pdb.post_mortem()

        raise


if __name__ == "__main__":
    run_normalizer()
