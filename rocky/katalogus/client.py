import json
from io import BytesIO
from typing import Annotated
from urllib.parse import quote

import httpx
import structlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_unicode_slug
from django.utils.translation import gettext as _
from httpx import HTTPError, HTTPStatusError, Response, codes
from jsonschema.exceptions import SchemaError
from jsonschema.validators import Draft202012Validator
from pydantic import AfterValidator, BaseModel, Field, field_serializer, field_validator
from tools.enums import SCAN_LEVEL
from tools.models import Organization, OrganizationMember

from octopoes.models import OOI
from octopoes.models.exception import TypeNotFound
from octopoes.models.types import type_by_name
from rocky.health import ServiceHealth

logger = structlog.get_logger("katalogus_client")


def valid_plugin_id(plugin_id: str) -> str:
    # plugin IDs should alphanumeric, including dashes, underscores and dots.
    if not plugin_id.replace("-", "").replace("_", "").replace(".", "").isalnum():
        raise ValueError("Plugin ID is not valid")

    return plugin_id


def valid_organization_code(organization_code: str) -> str:
    try:
        validate_unicode_slug(organization_code)
        return organization_code
    except ValidationError:
        raise ValueError("Organization code is not valid")


class Plugin(BaseModel):
    id: Annotated[str, AfterValidator(valid_plugin_id)]
    name: str
    version: str | None = None
    authors: str | None = None
    created: str | None = None
    description: str | None = None
    related: list[str] = Field(default_factory=list)
    type: str
    # TODO: this is the only field making a Plugin organization-specific. If we could separate the use of the enabled
    #  field from other uses, we would be able to drop the organization_code as an argument in a lot of places, hence
    #  simplifying the usage of the KATalogus for installation-wide operations (as plugins are not specific to an
    #  organization). One could argue that having this field here should mean we need an organization field as well to
    #  make sense out of it: for which organization is this plugin in fact enabled?
    enabled: bool

    def can_scan(self, member: OrganizationMember) -> bool:
        return member.has_perm("tools.can_scan_organization")


class Boefje(Plugin):
    scan_level: SCAN_LEVEL
    consumes: set[type[OOI]] = Field(default_factory=set)
    produces: set[str] = Field(default_factory=set)
    options: list[str] | None = None
    runnable_hash: str | None = None
    interval: int | None = None
    run_on: list[str] | None = None
    boefje_schema: dict | None = None
    oci_image: str | None = None
    oci_arguments: list[str] = Field(default_factory=list)

    # use a custom field_serializer for `consumes`
    @field_serializer("consumes")
    def serialize_consumes(self, consumes: set[type[OOI]]) -> set[str]:
        return {ooi_class.get_ooi_type() for ooi_class in consumes}

    @field_validator("boefje_schema")
    @classmethod
    def json_schema_valid(cls, boefje_schema: dict) -> dict | None:
        if boefje_schema is None:
            return None

        try:
            Draft202012Validator.check_schema(boefje_schema)
        except SchemaError as e:
            raise ValueError("The schema field is not a valid JSON schema") from e

        return boefje_schema

    def can_scan(self, member: OrganizationMember) -> bool:
        return super().can_scan(member) and member.has_clearance_level(self.scan_level.value)


class Normalizer(Plugin):
    consumes: set[str]
    produces: set[type[OOI]]

    # use a custom field_serializer for `produces`
    @field_serializer("produces")
    def serialize_produces(self, produces: set[type[OOI]]) -> set[str]:
        return {ooi_class.get_ooi_type() for ooi_class in produces}


class KATalogusError(Exception):
    @property
    def message(self):
        return self._message

    def __init__(self, message: str | None = None):
        if message is None:
            message = _("The KATalogus has an unexpected error. Check the logs for further details.")

        self._message = message

        super().__init__(message)

    def __str__(self):
        return self._message


class KATalogusHTTPStatusError(KATalogusError):
    def __init__(self, error: httpx.HTTPStatusError):
        self.error = error

        super().__init__(_("An HTTP %d error occurred. Check logs for more info.").format(error.response.status_code))


class KATalogusHTTPError(KATalogusError):
    def __init__(self, error: httpx.HTTPError):
        self.error = error

        super().__init__(_("An HTTP error occurred. Check logs for more info."))


class DuplicatePluginError(KATalogusError):
    def __init__(self, error_message: str):
        super().__init__(error_message)


class DuplicateNameError(KATalogusError):
    def __init__(self):
        super().__init__(_("Boefje with this name already exists."))


class DuplicateIdError(KATalogusError):
    def __init__(self):
        super().__init__(_("Boefje with this ID already exists."))


class KATalogusNotAllowedError(KATalogusError):
    def __init__(self, error_message: str):
        super().__init__(error_message)


def verify_response(response: Response) -> None:
    try:
        response.raise_for_status()
    except HTTPStatusError as error:
        response.read()

        if error.response.status_code == codes.BAD_REQUEST and "duplicate key" in error.response.text:
            raise DuplicatePluginError("Duplicate plugin name") from error

        if error.response.status_code == codes.BAD_REQUEST and "Duplicate plugin" in error.response.text:
            error_message = json.loads(error.response.text).get("detail")
            raise DuplicatePluginError(error_message) from error

        if error.response.status_code in [codes.FORBIDDEN, codes.NOT_FOUND]:
            raise KATalogusNotAllowedError(_("Access to resource not allowed")) from error

        raise KATalogusHTTPStatusError(error) from error
    except HTTPError as error:
        raise KATalogusError("KATalogus request failed") from error


class KATalogusClient:
    def __init__(self, base_uri: str):
        self.session = httpx.Client(
            base_url=base_uri,
            event_hooks={"response": [verify_response]},
            timeout=settings.ROCKY_OUTGOING_REQUEST_TIMEOUT,
        )

    def health(self) -> ServiceHealth:
        response = self.session.get("/health")

        return ServiceHealth.model_validate_json(response.content)

    def organization_exists(self, organization_code: str) -> bool:
        try:
            self.session.get(f"/v1/organisations/{quote(organization_code)}")
        except KATalogusNotAllowedError:
            return False

        return True

    def create_organization(self, organization):
        self.session.post("/v1/organisations/", json={"id": organization.code, "name": organization.name})

        logger.info("Created organization", name=organization.name)

    def delete_organization(self, organization_code: str):
        self.session.delete(f"/v1/organisations/{quote(organization_code)}")

        logger.info("Deleted organization", organization_code=organization_code)

    def get_plugins(self, organization_code: str, **params) -> list[Boefje | Normalizer]:
        response = self.session.get(f"/v1/organisations/{quote(organization_code)}/plugins", params=params)

        return [parse_plugin(plugin) for plugin in response.json()]

    def get_plugin(self, organization_code: str, plugin_id: str) -> Plugin:
        response = self.session.get(f"/v1/organisations/{quote(organization_code)}/plugins/{quote(plugin_id)}")

        return parse_plugin(response.json())

    def get_plugin_settings(self, organization_code: str, plugin_id: str) -> dict:
        response = self.session.get(f"/v1/organisations/{quote(organization_code)}/{quote(plugin_id)}/settings")

        return response.json()

    def upsert_plugin_settings(self, organization_code: str, plugin_id: str, values: dict) -> None:
        logger.info("Adding plugin settings", event_code=800023, plugin=plugin_id)
        self.session.put(f"/v1/organisations/{quote(organization_code)}/{quote(plugin_id)}/settings", json=values)

        logger.info("Upsert plugin settings", plugin_id=plugin_id)

    def delete_plugin_settings(self, organization_code: str, plugin_id: str) -> None:
        logger.info("Deleting plugin settings", event_code=800024, plugin=plugin_id)
        self.session.delete(f"/v1/organisations/{quote(organization_code)}/{quote(plugin_id)}/settings")

        logger.info("Deleted plugin settings", plugin_id=plugin_id)

    def clone_all_configuration_to_organization(self, from_organization: str, to_organization: str):
        to_organization = quote(to_organization)
        from_organization = quote(from_organization)
        logger.info("Cloning organization settings", event_code=910000, to_organization_code=to_organization)
        response = self.session.post(f"/v1/organisations/{from_organization}/settings/clone/{to_organization}")

        return response

    def get_normalizers(self, organization_code: str) -> list[Normalizer]:
        return self.get_plugins(organization_code, plugin_type="normalizer")

    def get_boefjes(self, organization_code: str) -> list[Boefje]:
        return self.get_plugins(organization_code, plugin_type="boefje")

    def enable_plugin(self, organization_code: str, plugin: Plugin) -> None:
        logger.info("Enabling plugin", event_code=800021, plugin=plugin.id)

        self._patch_plugin_state(organization_code, plugin.id, True)

    def enable_boefje_by_id(self, organization_code: str, boefje_id: str) -> None:
        self.enable_plugin(organization_code, self.get_plugin(organization_code, boefje_id))

    def disable_plugin(self, organization_code: str, plugin: Plugin) -> None:
        logger.info("Disabling plugin", event_code=800022, plugin=plugin.id)
        self._patch_plugin_state(organization_code, plugin.id, False)

    def get_enabled_boefjes(self, organization_code: str) -> list[Plugin]:
        return self.get_plugins(organization_code, plugin_type="boefje", state=True)

    def get_cover(self, organization_code: str, plugin_id: str) -> BytesIO:
        # TODO: does not need to be organization-specific
        response = self.session.get(
            f"/v1/organisations/{quote(organization_code)}/plugins/{quote(plugin_id)}/cover.jpg"
        )

        return BytesIO(response.content)

    def create_plugin(self, organization_code: str, plugin: Plugin) -> None:
        try:
            logger.info("Creating boefje", event_code=800025, boefje=plugin)
            response = self.session.post(
                f"/v1/organisations/{quote(organization_code)}/plugins",
                headers={"Content-Type": "application/json"},
                content=plugin.model_dump_json(exclude_none=True),
            )
            if response.status_code == codes.CREATED:
                logger.info("Plugin %s created", plugin.name)
            else:
                logger.info("Plugin %s could not be created", plugin.name)
        except KATalogusHTTPStatusError:
            logger.info("Plugin %s could not be created", plugin.name)
            raise

    def edit_plugin(self, organization_code: str, plugin: Plugin) -> None:
        try:
            logger.info("Editing boefje", event_code=800026, boefje=plugin.id)
            response = self.session.patch(
                f"/v1/organisations/{quote(organization_code)}/boefjes/{plugin.id}", content=plugin.model_dump_json()
            )
            if response.status_code == codes.NO_CONTENT:
                logger.info("Plugin %s updated", plugin.name)
            else:
                logger.info("Plugin %s could not be updated", plugin.name)
        except KATalogusHTTPStatusError:
            logger.info("Plugin %s could not be updated", plugin.name)
            raise

    def _patch_plugin_state(self, organization_code: str, plugin_id: str, enabled: bool) -> None:
        logger.info("Toggle plugin state", plugin_id=plugin_id, enabled=enabled)
        plugin_id = quote(plugin_id)

        self.session.patch(
            f"/v1/organisations/{quote(organization_code)}/plugins/{plugin_id}", json={"enabled": enabled}
        )


class KATalogus:
    """
    An adapter between the full KATalogusClient and the organization-specific context of most views. This restricts
    the set of available methods on the KATalogusClient and simplifies the interface by "currying" the organization
    into the relevant methods as an argument. We should use this class in the views to avoid making calls exposing
    information from other organizations users are not allowed to see.
    """

    def __init__(self, katalogus_client: KATalogusClient, member: OrganizationMember):
        self._katalogus_client = katalogus_client
        self._member = member

    def get_plugins(self, **params) -> list[Plugin]:
        return self._katalogus_client.get_plugins(self._member.organization.code, **params)

    def get_plugin(self, plugin_id: str) -> Plugin:
        return self._katalogus_client.get_plugin(self._member.organization.code, plugin_id)

    def get_plugin_settings(self, plugin_id: str) -> dict:
        if not self._member.has_perm("tools.can_view_katalogus_settings"):
            raise KATalogusNotAllowedError(_("User is not allowed to see plugin settings"))

        return self._katalogus_client.get_plugin_settings(self._member.organization.code, plugin_id)

    def upsert_plugin_settings(self, plugin_id: str, values: dict) -> None:
        if not self._member.has_perm("tools.can_set_katalogus_settings"):
            raise KATalogusNotAllowedError(_("User is not allowed to set plugin settings"))

        return self._katalogus_client.upsert_plugin_settings(self._member.organization.code, plugin_id, values)

    def delete_plugin_settings(self, plugin_id: str) -> None:
        if not self._member.has_perm("tools.can_set_katalogus_settings"):
            raise KATalogusNotAllowedError(_("User is not allowed to delete plugin settings"))

        return self._katalogus_client.delete_plugin_settings(self._member.organization.code, plugin_id)

    def clone_all_configuration_to_organization(self, to_organization: str):
        if not self._member.has_perm("tools.can_view_katalogus_settings"):
            raise KATalogusNotAllowedError(_("User is not allowed to view plugin settings"))

        try:
            to_member = OrganizationMember.objects.get(user=self._member.user, organization__code=to_organization)
        except Organization.DoesNotExist:
            raise
        except OrganizationMember.DoesNotExist:
            if not self._member.user.has_perm("tools.can_access_all_organizations"):
                raise KATalogusNotAllowedError(_("User is not allowed to access the other organization"))
            if not self._member.user.has_perm("tools.can_set_katalogus_settings"):
                raise KATalogusNotAllowedError(_("User is not allowed to set plugin settings"))
        else:
            if to_member.blocked:
                raise KATalogusNotAllowedError(_("User is not allowed to access the other organization"))

            if not to_member.has_perm("tools.can_set_katalogus_settings"):
                raise KATalogusNotAllowedError(_("User is not allowed to set plugin settings"))

        return self._katalogus_client.clone_all_configuration_to_organization(
            self._member.organization.code, to_organization
        )

    def get_normalizers(self) -> list[Normalizer]:
        return self._katalogus_client.get_normalizers(self._member.organization.code)

    def get_boefjes(self) -> list[Boefje]:
        return self._katalogus_client.get_boefjes(self._member.organization.code)

    def enable_plugin(self, plugin: Plugin) -> None:
        if not self._member.has_perm("tools.can_enable_disable_boefje"):
            raise KATalogusNotAllowedError(_("User is not allowed to enable plugins"))

        return self._katalogus_client.enable_plugin(self._member.organization.code, plugin)

    def enable_boefje_by_id(self, boefje_id: str) -> None:
        if not self._member.has_perm("tools.can_enable_disable_boefje"):
            raise KATalogusNotAllowedError(_("User is not allowed to enable plugins"))

        return self._katalogus_client.enable_boefje_by_id(self._member.organization.code, boefje_id)

    def disable_plugin(self, plugin: Plugin) -> None:
        if not self._member.has_perm("tools.can_enable_disable_boefje"):
            raise KATalogusNotAllowedError(_("User is not allowed to disable plugins"))

        return self._katalogus_client.disable_plugin(self._member.organization.code, plugin)

    def get_enabled_boefjes(self) -> list[Boefje]:
        return self._katalogus_client.get_plugins(self._member.organization.code, plugin_type="boefje", state=True)

    def get_cover(self, plugin_id: str) -> BytesIO:
        return self._katalogus_client.get_cover(self._member.organization.code, plugin_id)

    def create_plugin(self, plugin: Plugin) -> None:
        if not self._member.has_perm("tools.can_add_boefje"):
            raise KATalogusNotAllowedError(_("User is not allowed to create plugins"))

        return self._katalogus_client.create_plugin(self._member.organization.code, plugin)

    def edit_plugin(self, plugin: Plugin) -> None:
        if not self._member.has_perm("tools.can_add_boefje"):
            raise KATalogusNotAllowedError(_("User is not allowed to edit plugins"))

        return self._katalogus_client.edit_plugin(self._member.organization.code, plugin)


def parse_boefje(boefje: dict) -> Boefje:
    scan_level = SCAN_LEVEL(boefje["scan_level"])

    consumes = set()

    for type_name in boefje.get("consumes", []):
        try:
            consumes.add(type_by_name(type_name))
        except TypeNotFound:
            logger.warning("Unknown OOI type %s for boefje consumes %s", type_name, boefje["id"])

    return Boefje(
        id=boefje["id"],
        name=boefje.get("name") or boefje["id"],
        created=boefje.get("created"),
        description=boefje.get("description"),
        interval=boefje.get("interval"),
        run_on=boefje.get("run_on"),
        enabled=boefje["enabled"],
        type=boefje["type"],
        scan_level=scan_level,
        consumes=consumes,
        produces=boefje["produces"],
        boefje_schema=boefje.get("boefje_schema"),
        oci_image=boefje.get("oci_image"),
        oci_arguments=boefje.get("oci_arguments", []),
    )


def parse_normalizer(normalizer: dict) -> Normalizer:
    consumes = set(normalizer["consumes"])
    consumes.add(f"normalizer/{normalizer['id']}")
    produces = set()
    for type_name in normalizer.get("produces", []):
        try:
            produces.add(type_by_name(type_name))
        except TypeNotFound:
            logger.warning("Unknown OOI type %s for normalizer produces %s", type_name, normalizer["id"])

    return Normalizer(
        id=normalizer["id"],
        name=normalizer["name"],
        description=normalizer["description"],
        enabled=normalizer["enabled"],
        type=normalizer["type"],
        consumes=consumes,
        produces=produces,
    )


def parse_plugin(plugin: dict) -> Boefje | Normalizer:
    if plugin["type"] == "boefje":
        return parse_boefje(plugin)
    elif plugin["type"] == "normalizer":
        return parse_normalizer(plugin)
    else:
        raise Exception(f"Unknown plugin type: {plugin['type']}")


def get_katalogus_client() -> KATalogusClient:
    return KATalogusClient(settings.KATALOGUS_API)


def get_katalogus(member: OrganizationMember) -> KATalogus:
    return KATalogus(get_katalogus_client(), member)
