import os
import traceback
from base64 import b64encode
from datetime import datetime, timezone
from typing import Literal

import structlog

from .interfaces import BoefjeOutput, BoefjeStorageInterface, File, Handler, JobRuntimeError, StatusEnum, Task
from .job_models import BoefjeMeta
from .repository import BoefjeResource, LocalPluginRepository, _default_mime_types

logger = structlog.get_logger(__name__)

MIMETYPE_MIN_LENGTH = 5  # two chars before, and 2 chars after the slash ought to be reasonable


class TemporaryEnvironment:
    """Context manager that temporarily clears the environment vars and restores it after exiting the context"""

    def __init__(self):
        self._original_environment = os.environ.copy()

    def __enter__(self):
        os.environ.clear()
        return os.environ

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.environ.clear()
        os.environ.update(self._original_environment)


class BoefjeHandler(Handler):
    def __init__(self, local_repository: LocalPluginRepository, boefje_storage: BoefjeStorageInterface):
        self.local_repository = local_repository
        self.boefje_storage = boefje_storage

    def handle(self, task: Task) -> tuple[BoefjeMeta, list[tuple[set, bytes | str]]] | None | Literal[False]:
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
                raise JobRuntimeError("Not runnable module found")

            with TemporaryEnvironment() as temporary_environment:
                temporary_environment.update(boefje_meta.environment or {})
                # Until we fully switch over to the Boefje API, we need the start and end time here as a fallback.
                boefje_meta.started_at = datetime.now(timezone.utc)
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
                    tags=set(
                        _default_mime_types(boefje_meta.boefje).union(valid_mimetypes)
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

        return boefje_meta, boefje_results
