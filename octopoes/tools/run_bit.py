#!/usr/bin/env python3
# ruff: noqa: E402

import logging
import pdb
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

sys.path.append(str(Path(__file__).resolve().parent.parent))

from bits.definitions import get_bit_definitions

from octopoes.config.settings import Settings
from octopoes.core.app import bootstrap_octopoes, get_xtdb_client
from octopoes.models.exception import ObjectNotFoundException
from octopoes.models.origin import Origin, OriginParameter, OriginType
from octopoes.models.path import Path as OctopoesPath
from octopoes.xtdb.client import XTDBSession

logging.basicConfig(stream=sys.stdout, level=logging.INFO, force=True)


@click.command()
@click.option("--pdb", "start_pdb", is_flag=True, help="Start pdb on exceptions")
@click.argument("organization_code")
@click.argument("bit_id")
@click.argument("ooi")
def run_bit(start_pdb, organization_code, bit_id, ooi):
    """Run bit"""
    settings = Settings()

    valid_time = datetime.now(timezone.utc)

    session = XTDBSession(get_xtdb_client(str(settings.xtdb_uri), organization_code))
    octopoes_service = bootstrap_octopoes(settings, organization_code, session)
    ooi_repository = octopoes_service.ooi_repository
    origin_repository = octopoes_service.origin_repository
    origin_parameter_repository = octopoes_service.origin_parameter_repository

    ooi = ooi_repository.get(ooi, valid_time)

    bit_definition = get_bit_definitions()[bit_id]

    bit_instance = Origin(origin_type=OriginType.INFERENCE, method=bit_id, source=ooi.reference)

    try:
        try:
            origin_repository.get(bit_instance.id, valid_time)
        except ObjectNotFoundException:
            origin_repository.save(bit_instance, valid_time)

        for param_def in bit_definition.parameters:
            path = OctopoesPath.parse(f"{param_def.ooi_type.get_object_type()}.{param_def.relation_path}").reverse()

            param_oois = ooi_repository.list_related(ooi, path, valid_time=valid_time)
            for param_ooi in param_oois:
                param = OriginParameter(origin_id=bit_instance.id, reference=param_ooi.reference)
                origin_parameter_repository.save(param, valid_time)

        octopoes_service._run_inference(bit_instance, valid_time)
        octopoes_service.commit()
    except Exception:
        if start_pdb:
            pdb.post_mortem()

        raise


if __name__ == "__main__":
    run_bit()
