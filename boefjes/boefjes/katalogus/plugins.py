import datetime

import structlog
from croniter import croniter
from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse, Response
from jsonschema.exceptions import SchemaError
from jsonschema.validators import Draft202012Validator
from pydantic import BaseModel, Field, field_validator

from boefjes.dependencies.plugins import (
    PluginService,
    get_pagination_parameters,
    get_plugin_service,
    get_plugins_filter_parameters,
)
from boefjes.sql.db_models import RunOn
from boefjes.sql.plugin_storage import get_plugin_storage
from boefjes.storage.interfaces import DuplicatePlugin, IntegrityError, NotAllowed, PluginStorage, UniqueViolation
from boefjes.worker.models import FilterParameters, PaginationParameters, PluginType

router = APIRouter(prefix="/organisations/{organisation_id}", tags=["plugins"])

logger = structlog.get_logger(__name__)


# check if query matches plugin id, name or description
def _plugin_matches_query(plugin: PluginType, query: str) -> bool:
    return (
        query in plugin.id
        or (plugin.name is not None and query in plugin.name)
        or (plugin.description is not None and query in plugin.description)
    )


# todo: sorting?
@router.get("/plugins", response_model=list[PluginType])
def list_plugins(
    organisation_id: str,
    filter_params: FilterParameters = Depends(get_plugins_filter_parameters),
    pagination_params: PaginationParameters = Depends(get_pagination_parameters),
    plugin_service: PluginService = Depends(get_plugin_service),
) -> list[PluginType]:
    if filter_params.ids:
        try:
            with plugin_service as service:
                plugins = service.by_plugin_ids(filter_params.ids, organisation_id)
        except KeyError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Plugin not found")
    else:
        with plugin_service as service:
            plugins = service.get_all(organisation_id)

    # filter plugins by id, name or description
    if filter_params.q is not None:
        plugins = [plugin for plugin in plugins if _plugin_matches_query(plugin, filter_params.q)]

    # filter plugins by type
    if filter_params.type is not None:
        plugins = [plugin for plugin in plugins if plugin.type == filter_params.type]

    # filter plugins by state
    if filter_params.state is not None:
        plugins = [plugin for plugin in plugins if plugin.enabled is filter_params.state]

    # filter plugins by oci_image
    if filter_params.oci_image is not None:
        plugins = [
            plugin for plugin in plugins if plugin.type == "boefje" and plugin.oci_image == filter_params.oci_image
        ]

    # filter plugins by scan level for boefje plugins
    plugins = [plugin for plugin in plugins if plugin.type != "boefje" or plugin.scan_level >= filter_params.scan_level]

    if filter_params.consumes is not None:
        plugins = [plugin for plugin in plugins if filter_params.consumes.intersection(set(plugin.consumes))]

    if filter_params.produces is not None:
        plugins = [plugin for plugin in plugins if filter_params.produces.intersection(set(plugin.produces))]

    if pagination_params.limit is None:
        return plugins[pagination_params.offset :]

    # paginate plugins
    return plugins[pagination_params.offset : pagination_params.offset + pagination_params.limit]


@router.get("/plugins/{plugin_id}", response_model=PluginType)
def get_plugin(
    plugin_id: str, organisation_id: str, plugin_service: PluginService = Depends(get_plugin_service)
) -> PluginType:
    try:
        with plugin_service as service:
            return service.by_plugin_id(plugin_id, organisation_id)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plugin not found")


@router.post("/plugins", status_code=status.HTTP_201_CREATED)
def add_plugin(plugin: PluginType, plugin_service: PluginService = Depends(get_plugin_service)):
    try:
        with plugin_service as service:
            plugin.static = False  # Creation through the API implies that these cannot be static

            if plugin.type == "boefje":
                return service.create_boefje(plugin)

            if plugin.type == "normalizer":
                return service.create_normalizer(plugin)
    except UniqueViolation as error:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Duplicate plugin: a plugin with this {error.field} already exists"
        )
    except DuplicatePlugin as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error.message)

    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Creation of Bits is not supported")


@router.patch("/plugins/{plugin_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_plugin_state(
    plugin_id: str,
    organisation_id: str,
    enabled: bool = Body(False, embed=True),
    plugin_service: PluginService = Depends(get_plugin_service),
):
    with plugin_service as p:
        p.set_enabled_by_id(plugin_id, organisation_id, enabled)


class BoefjeIn(BaseModel):
    """
    For patching, we need all fields to be optional, hence we overwrite the definition here.
    Also see https://fastapi.tiangolo.com/tutorial/body-updates/ as a reference.
    """

    name: str | None = None
    version: str | None = None
    created: datetime.datetime | None = None
    description: str | None = None
    scan_level: int = 1
    consumes: set[str] = Field(default_factory=set)
    produces: set[str] = Field(default_factory=set)
    boefje_schema: dict | None = None
    cron: str | None = None
    interval: int | None = None
    run_on: list[RunOn] | None = None
    oci_image: str | None = None
    oci_arguments: list[str] = Field(default_factory=list)

    @field_validator("boefje_schema")
    @classmethod
    def json_schema_valid(cls, schema: dict | None) -> dict | None:
        if schema is not None:
            try:
                Draft202012Validator.check_schema(schema)
            except SchemaError as e:
                raise ValueError("The schema field is not a valid JSON schema") from e

        return schema

    @field_validator("cron")
    @classmethod
    def cron_valid(cls, cron: str | None) -> str | None:
        if cron is not None:
            croniter(cron)  # Raises a ValueError

        return cron


@router.patch("/boefjes/{boefje_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_boefje(boefje_id: str, boefje: BoefjeIn, storage: PluginStorage = Depends(get_plugin_storage)):
    # todo: update boefje should be done in the plugin service
    try:
        with storage as p:
            try:
                p.update_boefje(boefje_id, boefje.model_dump(exclude_unset=True))
            except NotAllowed:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Updating a static plugin is not allowed")
    except IntegrityError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error.message)


@router.delete("/boefjes/{boefje_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_boefje(boefje_id: str, plugin_storage: PluginStorage = Depends(get_plugin_storage)):
    with plugin_storage as p:
        p.delete_boefje_by_id(boefje_id)


class NormalizerIn(BaseModel):
    """
    For patching, we need all fields to be optional, hence we overwrite the definition here.
    Also see https://fastapi.tiangolo.com/tutorial/body-updates/ as a reference.
    """

    name: str | None = None
    version: str | None = None
    created: datetime.datetime | None = None
    description: str | None = None
    consumes: list[str] = Field(default_factory=list)  # mime types (and/ or boefjes)
    produces: list[str] = Field(default_factory=list)  # oois


@router.patch("/normalizers/{normalizer_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_normalizer(
    normalizer_id: str, normalizer: NormalizerIn, storage: PluginStorage = Depends(get_plugin_storage)
):
    with storage as p:
        p.update_normalizer(normalizer_id, normalizer.model_dump(exclude_unset=True))


@router.delete("/normalizers/{normalizer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_normalizer(normalizer_id: str, plugin_storage: PluginStorage = Depends(get_plugin_storage)):
    with plugin_storage as p:
        p.delete_normalizer_by_id(normalizer_id)


@router.get("/plugins/{plugin_id}/schema.json", include_in_schema=False)
def get_plugin_schema(plugin_id: str, plugin_service: PluginService = Depends(get_plugin_service)) -> JSONResponse:
    with plugin_service as service:
        return JSONResponse(service.schema(plugin_id))


@router.get("/plugins/{plugin_id}/cover.jpg", include_in_schema=False)
def get_plugin_cover(plugin_id: str, plugin_service: PluginService = Depends(get_plugin_service)) -> FileResponse:
    return FileResponse(plugin_service.cover(plugin_id))


@router.get("/plugins/{plugin_id}/description.md", include_in_schema=False)
def get_plugin_description(
    plugin_id: str, organisation_id: str, plugin_service: PluginService = Depends(get_plugin_service)
) -> Response:
    return Response(plugin_service.description(plugin_id, organisation_id))


@router.post("/settings/clone/{to_org}")
def clone_settings(organisation_id: str, to_org: str, storage: PluginService = Depends(get_plugin_service)):
    with storage as store:
        store.clone_settings_to_organisation(organisation_id, to_org)
