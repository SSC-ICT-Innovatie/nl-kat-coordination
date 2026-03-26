import os
import traceback
from base64 import b64encode
from datetime import datetime, timezone
from typing import Literal

import structlog

from .interfaces import BoefjeHandler, BoefjeOutput, BoefjeStorageInterface, File, JobRuntimeError, StatusEnum, Task
from .job_models import BoefjeMeta
from .repository import BoefjeResource, LocalPluginRepository, _default_mime_types

logger = structlog.get_logger(__name__)

MIMETYPE_MIN_LENGTH = 5  # two chars before, and 2 chars after the slash ought to be reasonable


class TemporaryEnvironment:
    """Context manager that temporarily adds environment vars and restores the old env after exiting the context"""

    def __init__(self, additional_environment: dict):
        self._original_environment = os.environ.copy()
        os.environ.update(additional_environment)

    def __enter__(self):
        return os.environ

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.environ.clear()
        os.environ.update(self._original_environment)


def _copy_raw_files(
    storage: BoefjeStorageInterface, boefje_meta: BoefjeMeta, boefje_output: BoefjeOutput, duplicated_tasks: list[Task]
):
    for item in duplicated_tasks:
        new_boefje_meta = item.data
        new_boefje_meta.runnable_hash = boefje_meta.runnable_hash
        new_boefje_meta.environment = boefje_meta.environment
        new_boefje_meta.started_at = boefje_meta.started_at
        new_boefje_meta.ended_at = boefje_meta.ended_at

        storage.save_output(new_boefje_meta, boefje_output)

        logger.info("Saved raw files boefje %s[%s]", new_boefje_meta.boefje.id, new_boefje_meta.id)


class LocalBoefjeHandler(BoefjeHandler):
    def __init__(self, local_repository: LocalPluginRepository, boefje_storage: BoefjeStorageInterface):
        self.local_repository = local_repository
        self.boefje_storage = boefje_storage

    def handle(self, task: Task) -> tuple[BoefjeMeta, BoefjeOutput] | None | Literal[False]:
        boefje_meta = task.data

        if not isinstance(boefje_meta, BoefjeMeta):
            raise ValueError("Plugin id does not belong to a boefje")

        logger.info("Starting boefje %s[%s]", boefje_meta.boefje.id, str(boefje_meta.id))
        error = None

        try:
            logger.debug("Running local boefje plugin")

            try:
                # TODO: remove/change once all boefjes are oci images. This is now a "fallback".
                boefje_resource = self.local_repository.by_id(boefje_meta.boefje.id)
            except KeyError:
                if not boefje_meta.boefje.oci_image:
                    raise

                boefje_resource = self.local_repository.by_image(boefje_meta.boefje.oci_image)

            if not isinstance(boefje_resource, BoefjeResource):
                raise JobRuntimeError(f"Not a boefje: {boefje_meta.boefje.id}")

            if not boefje_resource.module:
                raise JobRuntimeError("No runnable module found")

            boefje_meta.started_at = datetime.now(timezone.utc)

            with TemporaryEnvironment(boefje_meta.environment or {}):
                boefje_results = boefje_resource.module.run(boefje_meta.model_dump())

            boefje_meta.ended_at = datetime.now(timezone.utc)
        except BaseException as e:
            logger.exception("Error running boefje %s[%s]", boefje_meta.boefje.id, str(boefje_meta.id))
            boefje_meta.ended_at = datetime.now(timezone.utc)
            boefje_results = [({"error/boefje"}, traceback.format_exc())]
            error = e

        logger.info("Saving to Bytes for boefje %s[%s]", boefje_meta.boefje.id, str(boefje_meta.id))

        if not boefje_results:
            logger.info("No results for boefje %s[%s]", boefje_meta.boefje.id, boefje_meta.id)
            return None

        files: list[File] = []

        for boefje_added_mime_types, output in boefje_results:
            valid_mimetypes = set()
            for mimetype in boefje_added_mime_types:
                if len(mimetype) < MIMETYPE_MIN_LENGTH or "/" not in mimetype:
                    logger.warning(
                        "Invalid mime-type encountered in output for boefje %s[%s]",
                        boefje_meta.boefje.id,
                        str(boefje_meta.id),
                    )
                else:
                    valid_mimetypes.add(mimetype)

            files.append(
                File(
                    name=str(len(files)),
                    content=(b64encode(output) if isinstance(output, bytes) else b64encode(output.encode())).decode(),
                    tags=_default_mime_types(boefje_meta.boefje).union(
                        valid_mimetypes
                    ),  # default mime-types are added through the API
                )
            )

        boefje_output = BoefjeOutput(
            status=StatusEnum.FAILED if error is not None else StatusEnum.COMPLETED, files=files
        )
        raw_file_ids = self.boefje_storage.save_output(boefje_meta, boefje_output)

        logger.info("Saved %s raw files for boefje %s[%s]", len(raw_file_ids), boefje_meta.boefje.id, boefje_meta.id)

        if error is not None:
            raise error

        return boefje_meta, boefje_output

    def copy_raw_files(
        self, task: Task, output: tuple[BoefjeMeta, BoefjeOutput] | Literal[False], duplicated_tasks: list[Task]
    ) -> None:
        if output is False:
            return  # Output belonged to a docker boefje

        boefje_meta, boefje_output = output

        _copy_raw_files(self.boefje_storage, boefje_meta, boefje_output, duplicated_tasks)
