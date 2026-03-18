import datetime
import os
import uuid
from functools import cache
from typing import Any

import httpx
import structlog
from httpx import Client, HTTPError, HTTPTransport, Response
from jsonschema import ValidationError
from jsonschema.validators import validate
from pydantic import TypeAdapter

from boefjes.config import settings
from boefjes.dependencies.plugins import PluginService
from boefjes.worker.interfaces import SchedulerClientInterface, Task, TaskPop, TaskStatus, WorkerManager
from boefjes.worker.job_models import BoefjeMeta
from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models import Reference
from octopoes.models.exception import ObjectNotFoundException

logger = structlog.get_logger(__name__)


class SchedulerAPIClient(SchedulerClientInterface):
    def __init__(
        self,
        plugin_service: PluginService,
        base_url: str,
        oci_images: list[str] | None = None,
        plugins: list[str] | None = None,
    ):
        self._session = Client(
            base_url=base_url, transport=HTTPTransport(retries=6), timeout=settings.outgoing_request_timeout
        )
        self.plugin_service = plugin_service
        self.oci_images = oci_images
        self.plugins = plugins

    @staticmethod
    def _verify_response(response: Response) -> None:
        response.raise_for_status()

    def pop_items(
        self, queue: WorkerManager.Queue, filters: dict[str, list[dict[str, Any]]] | None = None, limit: int | None = 1
    ) -> list[Task]:
        if not filters:
            filters = {"filters": []}
        if self.oci_images:
            filters["filters"].append(
                {"column": "data", "field": "boefje__oci_image", "operator": "in", "value": self.oci_images}
            )
        if self.plugins:
            filters["filters"].append(
                {"column": "data", "field": "boefje__id", "operator": "in", "value": self.plugins}
            )

        if queue.value == "normalizer":
            response = self._session.post(
                "/schedulers/normalizer/pop",
                json=filters if filters["filters"] else None,
                params={"limit": limit} if limit else None,
            )
        else:
            response = self._session.post(
                "/schedulers/boefje/pop",
                json=filters if filters["filters"] else None,
                params={"limit": limit} if limit else None,
            )
        self._verify_response(response)

        page = TypeAdapter(TaskPop | None).validate_json(response.content)

        if page is None:
            return []

        results = []
        for task in page.results:
            if isinstance(task.data, BoefjeMeta):
                try:
                    task.data = self._hydrate_boefje_meta(task.data)
                except (ValidationError, ObjectNotFoundException):
                    self.patch_task(task.id, TaskStatus.FAILED)
                    continue
            results.append(task)

        return results

    def push_item(self, p_item: Task) -> None:
        if p_item.scheduler_id not in ["boefje", "normalizer"]:
            raise ValueError("Invalid scheduler id")

        response = self._session.post(f"/schedulers/{p_item.scheduler_id}/push", content=p_item.model_dump_json())
        self._verify_response(response)

    def patch_task(self, task_id: uuid.UUID, status: TaskStatus) -> None:
        response = self._session.patch(f"/tasks/{task_id}", json={"status": status.value})
        self._verify_response(response)

    def get_task(self, task_id: uuid.UUID, hydrate: bool = True) -> Task:
        response = self._session.get(f"/tasks/{task_id}")
        self._verify_response(response)

        task = Task.model_validate_json(response.content)

        if hydrate and isinstance(task.data, BoefjeMeta):
            task.data = self._hydrate_boefje_meta(task.data)

        return task

    def _hydrate_boefje_meta(self, boefje_meta: BoefjeMeta) -> BoefjeMeta:
        with self.plugin_service as service:
            plugin = service.by_plugin_id(boefje_meta.boefje.id, boefje_meta.organization)

        # The octopoes API connector is organization-specific, where the client is generic.
        octopoes_api_connector = get_octopoes_api_connector(boefje_meta.organization)
        input_ooi = boefje_meta.input_ooi
        boefje_meta.arguments = {"oci_image": plugin.oci_image, "oci_arguments": plugin.oci_arguments}
        boefje_meta.runnable_hash = plugin.runnable_hash

        if input_ooi:
            reference = Reference.from_str(input_ooi)
            try:
                ooi = octopoes_api_connector.get(reference, valid_time=datetime.datetime.now(datetime.timezone.utc))
                boefje_meta.arguments["input"] = ooi.serialize()
            except ObjectNotFoundException:
                logger.info(
                    "Can't run boefje because OOI does not exist anymore",
                    reference=reference,
                    boefje_id=boefje_meta.boefje.id,
                    ooi=boefje_meta.input_ooi,
                    task_id=boefje_meta.id,
                )
                raise
        try:
            boefje_meta.environment = get_environment_settings(boefje_meta, plugin.boefje_schema)
        except ValidationError:
            logger.exception("The boefje environment was not set correctly")
            raise

        return boefje_meta


@cache
def boefje_env_variables() -> dict:
    """
    Return all environment variables that start with BOEFJE_. The returned
    keys have the BOEFJE_ prefix removed.
    """

    boefje_variables = {}
    for key, value in os.environ.items():
        if key.startswith("BOEFJE_"):
            boefje_variables[key.removeprefix("BOEFJE_")] = value

    return boefje_variables


def get_system_env_settings_for_boefje(allowed_keys: list[str]) -> dict:
    return {key: value for key, value in boefje_env_variables().items() if key in allowed_keys}


def get_environment_settings(boefje_meta: BoefjeMeta, schema: dict | None = None) -> dict[str, str]:
    try:
        katalogus_api = str(settings.katalogus_api).rstrip("/")
        response = httpx.get(
            f"{katalogus_api}/v1/organisations/{boefje_meta.organization}/{boefje_meta.boefje.id}/settings", timeout=30
        )
        response.raise_for_status()
    except HTTPError:
        logger.exception("Error getting environment settings")
        raise

    allowed_keys = schema.get("properties", []) if schema else []
    new_env = get_system_env_settings_for_boefje(allowed_keys)

    settings_from_katalogus = response.json()

    for key, value in settings_from_katalogus.items():
        if key in allowed_keys:
            new_env[key] = value

    # The schema, besides dictating that a boefje cannot run if it is not matched, also provides an extra safeguard:
    # it is possible to inject code if arguments are passed that "escape" the call to a tool. Hence, we should enforce
    # the schema somewhere and make the schema as strict as possible.
    if schema is not None:
        validate(instance=new_env, schema=schema)

    return {key: str(value) for key, value in new_env.items()}


def get_octopoes_api_connector(org_code: str) -> OctopoesAPIConnector:
    return OctopoesAPIConnector(str(settings.octopoes_api), org_code)
