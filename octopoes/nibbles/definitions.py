import importlib
import inspect
import pkgutil
from collections.abc import Callable, Iterable
from pathlib import Path
from types import MethodType, ModuleType
from typing import Any, get_origin

import structlog
from pydantic import BaseModel
from xxhash import xxh3_128_hexdigest as xxh3

from octopoes.models import OOI, Reference, ScanLevel

NIBBLES_DIR = Path(__file__).parent
NIBBLE_ATTR_NAME = "NIBBLE"
NIBBLE_FUNC_NAME = "nibble"
logger = structlog.get_logger(__name__)


class NibbleParameter(BaseModel):
    object_type: Any
    parser: str = "[]"
    optional: bool = False
    additional: set[type[OOI]] = set()
    min_scan_level: ScanLevel | None = None

    def __eq__(self, other):
        if isinstance(other, NibbleParameter):
            return vars(self) == vars(other)
        elif isinstance(other, type):
            return self.object_type == other
        else:
            return False

    @property
    def triggers(self) -> set[type[OOI]]:
        if (
            isinstance(self.object_type, type)
            and get_origin(self.object_type) is None
            and issubclass(self.object_type, OOI)
        ):
            return {self.object_type} | self.additional
        else:
            return self.additional


class NibbleDefinition(BaseModel):
    id: str
    signature: list[NibbleParameter]
    query: str | Callable[[list[Reference | None]], str] | None = None
    enabled: bool = True
    additional: set[type[OOI]] = set()
    _payload: MethodType | None = None
    _checksum: str | None = None

    def __call__(self, args: Iterable[OOI]) -> OOI | Iterable[OOI | None] | None:
        if self._payload is None:
            raise NotImplementedError
        else:
            return self._payload(*args)

    def __hash__(self):
        return hash(self.id)

    @property
    def _ini(self) -> dict[str, Any]:
        return {"id": self.id, "enabled": self.enabled, "checksum": self._checksum}

    @property
    def triggers(self) -> set[type[OOI]]:
        return set.union(*[sgn.triggers for sgn in self.signature]) | self.additional

    def has_scan_levels(self) -> bool:
        return any(param.min_scan_level is not None for param in self.signature)

    def check_scan_levels(self, scan_levels: list[ScanLevel]) -> bool:
        if scan_levels:
            return all(
                param.min_scan_level is None or level >= param.min_scan_level
                for param, level in zip(self.signature, scan_levels)
            )
        else:
            return not self.has_scan_levels()


def get_nibble_definitions() -> dict[str, NibbleDefinition]:
    nibble_definitions = {}

    for package in pkgutil.walk_packages([str(NIBBLES_DIR)]):
        if package.name in ["definitions", "runner"]:
            continue

        try:
            module: ModuleType = importlib.import_module(".nibble", f"{NIBBLES_DIR.name}.{package.name}")

            if hasattr(module, NIBBLE_ATTR_NAME):
                nibble_definition: NibbleDefinition = getattr(module, NIBBLE_ATTR_NAME)

                try:
                    payload: ModuleType = importlib.import_module(
                        f".{package.name}", f"{NIBBLES_DIR.name}.{package.name}"
                    )
                    if hasattr(payload, NIBBLE_FUNC_NAME):
                        nibble_definition._payload = getattr(payload, NIBBLE_FUNC_NAME)
                        nibble_definition._checksum = xxh3(inspect.getsource(module) + inspect.getsource(payload))
                    else:
                        logger.warning('module "%s" has no function %s', package.name, NIBBLE_FUNC_NAME)

                except ModuleNotFoundError:
                    logger.warning('package "%s" has no function nibble', package.name)

                nibble_definitions[nibble_definition.id] = nibble_definition

            else:
                logger.warning('module "%s" has no attribute %s', package.name, NIBBLE_ATTR_NAME)

        except ModuleNotFoundError:
            logger.warning('package "%s" has no module nibble', package.name)

    return nibble_definitions
