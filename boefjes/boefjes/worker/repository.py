import hashlib
import json
import pkgutil
from functools import cache, lru_cache
from importlib import import_module
from inspect import isfunction, signature
from json import JSONDecodeError
from pathlib import Path
from typing import Protocol

import structlog
from jsonschema.exceptions import SchemaError
from pydantic_core import ValidationError

from .models import Boefje, Normalizer, PluginType

logger = structlog.get_logger(__name__)

BOEFJES_DIR = Path(__file__).parent.parent / "plugins"
BOEFJE_DEFINITION_FILE = "boefje.json"
SCHEMA_FILE = "schema.json"
NORMALIZER_DEFINITION_FILE = "normalizer.json"
ENTRYPOINT_BOEFJES = "main.py"
ENTRYPOINT_NORMALIZERS = "normalize.py"


class ModuleException(Exception):
    """General error for modules"""


class Runnable(Protocol):
    def run(self, *args, **kwargs):
        raise NotImplementedError


class BoefjeResource:
    """Represents a Boefje package that we can run. Throws a ModuleException if any validation fails."""

    def __init__(self, path: Path, package: str, path_hash: str):
        self.path = path
        self.boefje: Boefje = Boefje.model_validate_json(path.joinpath(BOEFJE_DEFINITION_FILE).read_text())
        self.boefje.runnable_hash = path_hash
        self.boefje.produces = self.boefje.produces.union(set(_default_mime_types(self.boefje)))

        try:
            self.module: Runnable | None = get_runnable_module_from_package(
                package, ENTRYPOINT_BOEFJES, parameter_count=1
            )
        except ModuleException:
            self.module = None  # Most likely an OCI boefje

        if (path / SCHEMA_FILE).exists():
            try:
                self.boefje.boefje_schema = json.load((path / SCHEMA_FILE).open())
            except JSONDecodeError as e:
                raise ModuleException("Invalid schema file") from e
            except SchemaError as e:
                raise ModuleException("Invalid schema") from e


class NormalizerResource:
    """Represents a Normalizer package that we can run. Throws a ModuleException if any validation fails."""

    def __init__(self, path: Path, package: str):
        self.path = path
        self.normalizer = Normalizer.model_validate_json(path.joinpath(NORMALIZER_DEFINITION_FILE).read_text())
        self.normalizer.consumes.append(f"normalizer/{self.normalizer.id}")
        self.module = get_runnable_module_from_package(package, ENTRYPOINT_NORMALIZERS, parameter_count=2)


class LocalPluginRepository:
    def __init__(self, path: Path):
        self.path = path

    def get_all(self) -> list[PluginType]:
        boefjes = [resource.boefje for resource in self.resolve_boefjes().values()]
        normalizers = [resource.normalizer for resource in self.resolve_normalizers().values()]
        return boefjes + normalizers

    def by_id(self, plugin_id: str) -> BoefjeResource | NormalizerResource:
        boefjes = self.resolve_boefjes()

        if plugin_id in boefjes:
            return boefjes[plugin_id]

        normalizers = self.resolve_normalizers()

        if plugin_id in normalizers:
            return normalizers[plugin_id]

        raise KeyError(f"Can't find plugin {plugin_id}")

    def by_image(self, image: str) -> BoefjeResource:
        boefjes = self.resolve_boefjes()

        for boefje in boefjes.values():
            if boefje.boefje.oci_image == image:
                return boefje

        raise KeyError(f"Can't find image {image}")

    def by_name(self, plugin_name: str) -> BoefjeResource | NormalizerResource:
        boefjes = {resource.boefje.name: resource for resource in self.resolve_boefjes().values()}

        if plugin_name in boefjes:
            return boefjes[plugin_name]

        normalizers = {resource.normalizer.name: resource for resource in self.resolve_normalizers().values()}

        if plugin_name in normalizers:
            return normalizers[plugin_name]

        raise KeyError(f"Can't find plugin {plugin_name}")

    def schema(self, id_: str) -> dict | None:
        boefjes = self.resolve_boefjes()

        if id_ not in boefjes:
            return None

        path = boefjes[id_].path / SCHEMA_FILE

        if not path.exists():
            logger.debug("Did not find schema for boefje %s", id_)
            return None

        return json.loads(path.read_text())

    def cover_path(self, plugin_id: str) -> Path:
        boefjes = self.resolve_boefjes()
        normalizers = self.resolve_normalizers()
        default_cover_path = self.default_cover_path()
        plugin: BoefjeResource | NormalizerResource

        if plugin_id in boefjes:
            plugin = boefjes[plugin_id]
            cover_path = plugin.path / "cover.jpg"
        elif plugin_id in normalizers:
            plugin = normalizers[plugin_id]
            cover_path = plugin.path / "normalizer_cover.jpg"
        else:
            cover_path = default_cover_path

        if not cover_path.exists():
            logger.debug("Did not find cover for plugin %s", plugin_id)
            return default_cover_path

        return cover_path

    def default_cover_path(self) -> Path:
        return self.path / "default_cover.jpg"

    def description_path(self, id_: str) -> Path | None:
        boefjes = self.resolve_boefjes()

        if id_ not in boefjes:
            return None

        return boefjes[id_].path / "description.md"

    def resolve_boefjes(self) -> dict[str, BoefjeResource]:
        return _cached_resolve_boefjes(self.path)

    def resolve_normalizers(self) -> dict[str, NormalizerResource]:
        return _cached_resolve_normalizers(self.path)


@cache
def _cached_resolve_boefjes(path: Path) -> dict[str, BoefjeResource]:
    paths_and_packages = _find_packages_in_path_containing_files(path, (BOEFJE_DEFINITION_FILE,))
    boefje_resources = []

    for path, package in paths_and_packages:
        try:
            boefje_resources.append(get_boefje_resource(path, package, hash_path(path)))
        except (ModuleException, ValidationError):
            logger.exception("Error getting boefje resource")

    return {resource.boefje.id: resource for resource in boefje_resources}


@cache
def _cached_resolve_normalizers(path: Path) -> dict[str, NormalizerResource]:
    paths_and_packages = _find_packages_in_path_containing_files(
        path, (NORMALIZER_DEFINITION_FILE, ENTRYPOINT_NORMALIZERS)
    )
    normalizer_resources = []

    for path, package in paths_and_packages:
        try:
            normalizer_resources.append(get_normalizer_resource(path, package, hash_path(path)))
        except (ModuleException, ValidationError):
            logger.exception("Error getting normalizer resource")

    return {resource.normalizer.id: resource for resource in normalizer_resources}


def _find_packages_in_path_containing_files(path: Path, required_files: tuple[str, ...]) -> list[tuple[Path, str]]:
    prefix = create_relative_import_statement_from_cwd(path)
    paths = []

    for package in pkgutil.walk_packages([str(path)], prefix):
        if not package.ispkg:
            logger.debug("%s is not a package", package.name)
            continue

        new_path = path / package.name.replace(prefix, "").replace(".", "/")
        missing_files = [file for file in required_files if not (new_path / file).exists()]

        if missing_files:
            logger.debug("Files %s not found for %s", missing_files, package.name)
            continue

        paths.append((new_path, package.name))

    return paths


def create_relative_import_statement_from_cwd(package_dir: Path) -> str:
    relative_path = str(package_dir.absolute()).replace(str(Path.cwd()), "")  # e.g. "/boefjes/plugins"

    return f"{relative_path[1:].replace('/', '.')}." if relative_path else ""  # Turns into "boefjes.plugins."


@lru_cache(maxsize=200)
def get_boefje_resource(path: Path, package: str, path_hash: str):
    """The cache size in theory only has to be the amount of local boefjes available, but 200 gives us some extra
    space. Adding the hash to the arguments makes sure we refresh this."""

    return BoefjeResource(path, package, path_hash)


@lru_cache(maxsize=200)
def get_normalizer_resource(path: Path, package: str, path_hash: str):
    """The cache size in theory only has to be the amount of local normalizers available, but 200 gives us some extra
    space. Adding the hash to the arguments makes sure we refresh this."""

    return NormalizerResource(path, package)


def get_local_repository():
    return LocalPluginRepository(BOEFJES_DIR)


def get_runnable_module_from_package(package: str, module_file: str, *, parameter_count: int) -> Runnable:
    import_statement = f"{package}.{module_file.rstrip('.py')}"

    try:
        module = import_module(import_statement)
    except Exception as e:
        raise ModuleException(f"Cannot import module {import_statement}") from e

    if not hasattr(module, "run") or not isfunction(module.run):
        raise ModuleException(f"Module {module} does not define a run function")

    if len(signature(module.run).parameters) != parameter_count:
        raise ModuleException("Module entrypoint has wrong amount of parameters")

    return module


def hash_path(path: Path) -> str:
    """Returns sha256(file1 + file2 + ...) of all files in the given path."""

    folder_hash = hashlib.sha256()

    for file in sorted(path.glob("**/*")):
        # Note that the hash does not include *.pyc files
        # Thus there may be a desync between the source code and the cached, compiled bytecode
        if file.is_file() and file.suffix != ".pyc":
            with file.open("rb") as f:
                while chunk := f.read(32768):
                    folder_hash.update(chunk)

    return folder_hash.hexdigest()


def _default_mime_types(boefje: Boefje) -> set:
    mime_types = {f"boefje/{boefje.id}"}

    if boefje.version is not None:
        mime_types = mime_types.union({f"boefje/{boefje.id}-{boefje.version}"})

    return mime_types
