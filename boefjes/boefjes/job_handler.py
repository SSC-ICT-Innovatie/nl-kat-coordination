from collections.abc import Callable
from datetime import datetime, timezone
from typing import Literal, cast

import docker
import structlog
from docker.errors import APIError, ContainerError, ImageNotFound
from httpx import HTTPError

from boefjes.clients.bytes_client import BytesAPIClient
from boefjes.clients.scheduler_client import SchedulerAPIClient, get_octopoes_api_connector
from boefjes.config import settings
from boefjes.normalizer_interfaces import NormalizerJobRunner
from boefjes.worker.boefje_handler import BoefjeHandler
from boefjes.worker.interfaces import Handler, Task, TaskStatus
from boefjes.worker.job_models import BoefjeMeta
from boefjes.worker.repository import _default_mime_types
from octopoes.api.models import Affirmation, Declaration, Observation
from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models import Reference, ScanLevel

logger = structlog.get_logger(__name__)

bytes_api_client = BytesAPIClient(
    str(settings.bytes_api), username=settings.bytes_username, password=settings.bytes_password
)


class DockerBoefjeHandler(Handler):
    CACHE_VOLUME_NAME = "openkat_cache"
    CACHE_VOLUME_TARGET = "/home/nonroot/openkat_cache"

    def __init__(self, scheduler_client: SchedulerAPIClient, bytes_api_client: BytesAPIClient):
        self.docker_client = docker.from_env()
        self.scheduler_client = scheduler_client
        self.bytes_api_client = bytes_api_client

    def handle(self, task: Task) -> tuple[BoefjeMeta, list[tuple[set, bytes | str]]] | None | Literal[False]:
        boefje_meta = task.data
        oci_image = boefje_meta.arguments["oci_image"]

        if not oci_image:
            raise RuntimeError("Boefje does not have OCI image")

        stderr_mime_types = _default_mime_types(boefje_meta.boefje)
        task_id = boefje_meta.id
        boefje_meta.started_at = datetime.now(timezone.utc)

        try:
            input_url = str(settings.api).rstrip("/") + f"/api/v0/tasks/{task_id}"
            container_logs = self.docker_client.containers.run(
                image=oci_image,
                name="kat_boefje_" + str(task_id),
                command=input_url,
                stdout=False,
                stderr=True,
                remove=True,
                network=settings.docker_network,
                volumes=[f"{self.CACHE_VOLUME_NAME}:{self.CACHE_VOLUME_TARGET}"],
            )

            task = self.scheduler_client.get_task(task_id)

            # if status is still running the container didn't call the output API endpoint, so set to status to failed
            if task.status == TaskStatus.RUNNING:
                boefje_meta.ended_at = datetime.now(timezone.utc)
                self.bytes_api_client.save_boefje_meta(boefje_meta)  # The task didn't create a boefje_meta object
                self.bytes_api_client.save_raws(task_id, container_logs, stderr_mime_types.union({"error/boefje"}))
                self.scheduler_client.patch_task(task_id, TaskStatus.FAILED)

                # have to raise exception to prevent _start_working function from setting status to completed
                raise RuntimeError("Boefje did not call output API endpoint")
        except ContainerError as e:
            logger.error(
                "Container for task %s failed and returned exit status %d, stderr saved to bytes",
                task_id,
                e.exit_status,
            )

            # save container log (stderr) to bytes
            self.bytes_api_client.login()
            boefje_meta.ended_at = datetime.now(timezone.utc)
            try:
                # this boefje_meta might be incomplete, it comes from the scheduler instead of the Boefje I/O API
                self.bytes_api_client.save_boefje_meta(boefje_meta)
            except HTTPError:
                logger.error("Failed to save boefje meta to bytes, continuing anyway")
            self.bytes_api_client.save_raw(task_id, e.stderr, stderr_mime_types)
            self.scheduler_client.patch_task(task_id, TaskStatus.FAILED)
        except ImageNotFound:
            logger.error("Docker image %s not found", oci_image)
            self.scheduler_client.patch_task(task_id, TaskStatus.FAILED)
        except APIError as e:
            logger.error("Docker API error: %s", e)
            self.scheduler_client.patch_task(task_id, TaskStatus.FAILED)

        return False


class NormalizerHandler(Handler):
    def __init__(
        self,
        job_runner: NormalizerJobRunner,
        bytes_client: BytesAPIClient,
        whitelist: dict[str, int] | None = None,
        octopoes_factory: Callable[[str], OctopoesAPIConnector] = get_octopoes_api_connector,
    ):
        self.job_runner = job_runner
        self.bytes_client: BytesAPIClient = bytes_client
        self.whitelist = whitelist or {}
        self.octopoes_factory = octopoes_factory

    def handle(self, task: Task):
        normalizer_meta = task.data
        logger.info("Handling normalizer %s[%s]", normalizer_meta.normalizer.id, normalizer_meta.id)

        raw = self.bytes_client.get_raw(normalizer_meta.raw_data.id)

        normalizer_meta.started_at = datetime.now(timezone.utc)

        try:
            results = self.job_runner.run(normalizer_meta, raw)
            connector = self.octopoes_factory(normalizer_meta.raw_data.boefje_meta.organization)

            logger.info("Obtained results %s", str(results))

            for observation in results.observations:
                for ooi in observation.results:
                    if ooi.primary_key == observation.input_ooi:
                        logger.warning(
                            'Normalizer "%s" returned input [%s]', normalizer_meta.normalizer.id, observation.input_ooi
                        )
                reference = Reference.from_str(observation.input_ooi)
                connector.save_observation(
                    Observation(
                        method=normalizer_meta.normalizer.id,
                        source=reference,
                        source_method=normalizer_meta.raw_data.boefje_meta.boefje.id,
                        task_id=normalizer_meta.id,
                        valid_time=normalizer_meta.raw_data.boefje_meta.ended_at,
                        result=[ooi for ooi in observation.results if ooi.primary_key != observation.input_ooi],
                    )
                )

            for declaration in results.declarations:
                connector.save_declaration(
                    Declaration(
                        method=normalizer_meta.normalizer.id,
                        source_method=normalizer_meta.raw_data.boefje_meta.boefje.id,
                        ooi=declaration.ooi,
                        task_id=normalizer_meta.id,
                        valid_time=normalizer_meta.raw_data.boefje_meta.ended_at,
                    )
                )

            for affirmation in results.affirmations:
                connector.save_affirmation(
                    Affirmation(
                        method=normalizer_meta.normalizer.id,
                        source_method=normalizer_meta.raw_data.boefje_meta.boefje.id,
                        ooi=affirmation.ooi,
                        task_id=normalizer_meta.id,
                        valid_time=normalizer_meta.raw_data.boefje_meta.ended_at,
                    )
                )

            if (
                normalizer_meta.raw_data.boefje_meta.input_ooi  # No input OOI means no deletion propagation
                and not (results.observations or results.declarations or results.affirmations)
            ):
                # There were no results found, which we still need to signal to Octopoes for deletion propagation

                connector.save_observation(
                    Observation(
                        method=normalizer_meta.normalizer.id,
                        source=Reference.from_str(normalizer_meta.raw_data.boefje_meta.input_ooi),
                        source_method=normalizer_meta.raw_data.boefje_meta.boefje.id,
                        task_id=normalizer_meta.id,
                        valid_time=normalizer_meta.raw_data.boefje_meta.ended_at,
                        result=[],
                    )
                )

            corrected_scan_profiles = []
            for profile in results.scan_profiles:
                profile.level = ScanLevel(
                    min(profile.level, self.whitelist.get(normalizer_meta.normalizer.id, profile.level))
                )
                corrected_scan_profiles.append(profile)

            validated_scan_profiles = [
                profile
                for profile in corrected_scan_profiles
                if self.whitelist and profile.level <= self.whitelist.get(normalizer_meta.normalizer.id, -1)
            ]
            if validated_scan_profiles:
                connector.save_many_scan_profiles(
                    results.scan_profiles,
                    # Mypy doesn't seem to be able to figure out that ended_at is a datetime
                    valid_time=cast(datetime, normalizer_meta.raw_data.boefje_meta.ended_at),
                )
        finally:
            normalizer_meta.ended_at = datetime.now(timezone.utc)
            self.bytes_client.save_normalizer_meta(normalizer_meta)

        logger.info("Done with normalizer %s[%s]", normalizer_meta.normalizer.id, normalizer_meta.id)


class CompositeBoefjeHandler(Handler):
    """This is a pattern that allows us to use the Handler interface while allowing multiple handlers to be active at
    the same time, depending on the configuration. This way, we don't need to keep the option to delegate in every
    BoefjeHandler instance."""

    def __init__(self, boefje_handler: BoefjeHandler | None = None, docker_handler: DockerBoefjeHandler | None = None):
        self.boefje_handler = boefje_handler
        self.docker_handler = docker_handler

    def handle(self, task: Task) -> tuple[BoefjeMeta, list[tuple[set, bytes | str]]] | None | Literal[False]:
        if not isinstance(task.data, BoefjeMeta):
            raise RuntimeError("Did not receive boefje task")

        if self.docker_handler and task.data.arguments["oci_image"]:
            logger.info(
                "Delegating boefje %s[task_id=%s] to Docker runner with OCI image [%s]",
                task.data.boefje.id,
                str(task.data.id),
                task.data.arguments["oci_image"],
            )
            return self.docker_handler.handle(task)

        if not self.boefje_handler:
            raise RuntimeError("No handlers defined")

        return self.boefje_handler.handle(task)
