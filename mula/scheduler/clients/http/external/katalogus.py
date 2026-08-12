import threading

import httpx

from scheduler.clients.errors import exception_handler
from scheduler.clients.http import HTTPService
from scheduler.models import Boefje, BoefjeConfig, Organisation, Plugin


class Katalogus(HTTPService):
    """A class that provides methods to interact with the Katalogus API."""

    name = "katalogus"

    def __init__(self, host: str, source: str, timeout: int, pool_connections: int):
        super().__init__(host, source, timeout, pool_connections)

        # For every organisation we cache which new boefjes for an organisation
        # have been enabled.
        self.new_boefjes_cache_lock = threading.Lock()
        self.new_boefjes_cache: dict = {}

    @exception_handler
    def get_boefjes(self) -> list[Boefje]:
        url = f"{self.host}/boefjes"
        try:
            response = self.get(url)
            return [Boefje(**boefje) for boefje in response.json()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.NOT_FOUND:
                return []
            raise

    @exception_handler
    def get_boefje(self, boefje_id: str) -> Boefje | None:
        url = f"{self.host}/boefjes/{boefje_id}"
        try:
            response = self.get(url)
            return Boefje(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.NOT_FOUND:
                return None
            raise

    @exception_handler
    def get_organisation(self, organisation_id) -> Organisation | None:
        url = f"{self.host}/v1/organisations/{organisation_id}"
        try:
            response = self.get(url)
            return Organisation(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.NOT_FOUND:
                return None
            raise

    @exception_handler
    def get_organisations(self) -> list[Organisation]:
        url = f"{self.host}/v1/organisations"
        try:
            response = self.get(url)
            return [Organisation(**organisation) for organisation in response.json().values()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.NOT_FOUND:
                return []
            raise

    @exception_handler
    def get_plugins_by_organisation(self, organisation_id: str) -> list[Plugin]:
        url = f"{self.host}/v1/organisations/{organisation_id}/plugins"
        try:
            response = self.get(url)
            return [Plugin(**plugin) for plugin in response.json()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.NOT_FOUND:
                return []
            raise

    @exception_handler
    def get_plugin_by_id_and_org_id(self, plugin_id: str, organisation_id: str) -> Plugin | None:
        url = f"{self.host}/v1/organisations/{organisation_id}/plugins/{plugin_id}"

        try:
            response = self.get(url)
            return Plugin(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.NOT_FOUND:
                return None
            raise

    @exception_handler
    def get_boefjes_by_type_and_org_id(self, ooi_type: str, organisation_id: str) -> list[Plugin]:
        url = f"{self.host}/v1/organisations/{organisation_id}/plugins"

        try:
            response = self.get(url, params={"plugin_type": "boefje", "consumes": [ooi_type]})
            return [Plugin(**plugin) for plugin in response.json()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.NOT_FOUND:
                return []
            raise

    @exception_handler
    def get_normalizers_by_org_id_and_type(self, organisation_id: str, ooi_type: str) -> list[Plugin]:
        url = f"{self.host}/v1/organisations/{organisation_id}/plugins"
        try:
            response = self.get(url, params={"plugin_type": "normalizer", "consumes": [ooi_type]})
            return [Plugin(**plugin) for plugin in response.json()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.NOT_FOUND:
                return []
            raise

    def get_new_boefjes_by_org_id(self, organisation_id: str) -> list[Plugin]:
        with self.new_boefjes_cache_lock:
            # Get the enabled boefjes for the organisation from katalogus
            plugins = self.get_plugins_by_organisation(organisation_id)
            enabled_boefjes = {
                plugin.id: plugin
                for plugin in plugins
                if plugin.enabled is True and plugin.type == "boefje" and plugin.consumes
            }

            # Check if there are new boefjes
            new_boefjes = []
            for boefje_id, boefje in enabled_boefjes.items():
                if boefje_id not in self.new_boefjes_cache.get(organisation_id, {}):
                    new_boefjes.append(boefje)

            # Update the cache
            self.new_boefjes_cache[organisation_id] = enabled_boefjes

            self.logger.debug(
                "%d new boefjes found for organisation %s",
                len(new_boefjes),
                organisation_id,
                organisation_id=organisation_id,
                boefjes=[boefje.name for boefje in new_boefjes],
            )

            return new_boefjes

    def get_configs(
        self,
        organisation_id: str,
        boefje_id: str | None = None,
        enabled: bool | None = None,
        with_duplicates: bool = False,
        offset: int = 0,
        limit: int = 0,
    ) -> list[BoefjeConfig]:
        url = f"{self.host}/v1/configs"
        try:
            response = self.get(
                url,
                params={
                    "organisation_id": organisation_id,
                    "boefje_id": boefje_id,
                    "enabled": enabled,
                    "with_duplicates": with_duplicates,
                    "offset": offset,
                    "limit": limit,
                },
            )
            return [BoefjeConfig(**config) for config in response.json()]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.NOT_FOUND:
                return []
            raise
