import re
from abc import ABC

from boefjes.worker.models import Boefje, BoefjeConfig, Normalizer, Organisation, PluginType


class StorageError(Exception):
    """Generic exception for persistence"""

    def __init__(self, message: str):
        self.message = message


class IntegrityError(StorageError):
    """Integrity error during persistence of an entity"""

    def __init__(self, message: str):
        self.message = message


class UniqueViolation(IntegrityError):
    def __init__(self, message: str):
        self.field = self._get_field_name(message)
        self.message = message

    def _get_field_name(self, message: str) -> str | None:
        matches = re.findall(r"Key \((.*)\)=", message)

        if matches:
            return matches[0]

        return None


class SettingsNotConformingToSchema(StorageError):
    def __init__(self, plugin_id: str, validation_error: str):
        super().__init__(f"Settings for plugin {plugin_id} are not conform the plugin schema: {validation_error}")


class NotFound(StorageError):
    """Generic exception for when objects are not found"""


class OrganisationNotFound(NotFound):
    def __init__(self, organisation_id: str):
        super().__init__(f"Organisation with id '{organisation_id}' not found")


class PluginNotFound(NotFound):
    def __init__(self, plugin_id: str):
        super().__init__(f"Plugin with id '{plugin_id}' not found")


class PluginStateNotFound(NotFound):
    def __init__(self, plugin_id: str, organisation_id: str):
        super().__init__(f"State for plugin with id '{plugin_id}' not found for organisation '{organisation_id}'")


class ConfigNotFound(NotFound):
    def __init__(self, organisation_id: str, plugin_id: str):
        super().__init__(f"Setting not found for organisation '{organisation_id}' and plugin '{plugin_id}'")


class NotAllowed(StorageError):
    """Generic exception for operations that are not allowed at a domain level"""


class CannotUpdateStaticPlugin(NotAllowed):
    def __init__(self, plugin_id: str):
        super().__init__(f"Plugin with id '{plugin_id}' is static, so updating it is not allowed")


class DuplicatePlugin(NotAllowed):
    def __init__(self, field: str | None):
        super().__init__(f"Duplicate plugin: a plugin with this {field} already exists")


class OrganisationStorage(ABC):
    def __enter__(self):
        return self

    def __exit__(self, exc_type: type[Exception], exc_value: str, exc_traceback: str) -> None:  # noqa: F841
        pass

    def get_by_id(self, organisation_id: str) -> Organisation:
        raise NotImplementedError

    def get_all(self) -> dict[str, Organisation]:
        raise NotImplementedError

    def create(self, organisation: Organisation) -> None:
        raise NotImplementedError

    def update(self, organisation: Organisation) -> None:
        raise NotImplementedError

    def delete_by_id(self, organisation_id: str) -> None:
        raise NotImplementedError


class PluginStorage(ABC):
    def __enter__(self):
        return self

    def __exit__(self, exc_type: type[Exception], exc_value: str, exc_traceback: str) -> None:  # noqa: F841
        pass

    def get_all(self) -> list[PluginType]:
        raise NotImplementedError

    def boefje_by_id(self, boefje_id: str) -> Boefje:
        raise NotImplementedError

    def normalizer_by_id(self, normalizer_id: str) -> Normalizer:
        raise NotImplementedError

    def create_boefje(self, boefje: Boefje) -> None:
        raise NotImplementedError

    def create_normalizer(self, normalizer: Normalizer) -> None:
        raise NotImplementedError

    def update_boefje(self, boefje_id: str, data: dict) -> None:
        raise NotImplementedError

    def update_normalizer(self, normalizer_id: str, data: dict) -> None:
        raise NotImplementedError

    def delete_boefje_by_id(self, boefje_id: str) -> None:
        raise NotImplementedError

    def delete_normalizer_by_id(self, normalizer_id: str) -> None:
        raise NotImplementedError


class ConfigStorage(ABC):
    def __enter__(self):
        return self

    def __exit__(self, exc_type: type[Exception], exc_value: str, exc_traceback: str) -> None:  # noqa: F841
        pass

    def get_all_settings(self, organisation_id: str, plugin_id: str) -> dict[str, str]:
        raise NotImplementedError

    def upsert(
        self, organisation_id: str, plugin_id: str, settings: dict | None = None, enabled: bool | None = None
    ) -> None:
        raise NotImplementedError

    def delete(self, organisation_id: str, plugin_id: str) -> None:
        raise NotImplementedError

    def is_enabled_by_id(self, plugin_id: str, organisation_id: str) -> bool:
        raise NotImplementedError

    def get_enabled_boefjes(self, organisation_id: str) -> list[str]:
        raise NotImplementedError

    def get_enabled_normalizers(self, organisation_id: str) -> list[str]:
        raise NotImplementedError

    def get_disabled_boefjes(self, organisation_id: str) -> list[str]:
        raise NotImplementedError

    def get_disabled_normalizers(self, organisation_id: str) -> list[str]:
        raise NotImplementedError

    def get_states_for_organisation(self, organisation_id: str) -> dict[str, bool]:
        raise NotImplementedError

    def list_boefje_configs(
        self,
        offset: int,
        limit: int,
        organisation_id: str | None = None,
        boefje_id: str | None = None,
        enabled: bool | None = None,
        with_duplicates: bool = False,  # Only has effect if both organisation_id and boefje_id are set
    ) -> list[BoefjeConfig]:
        raise NotImplementedError
