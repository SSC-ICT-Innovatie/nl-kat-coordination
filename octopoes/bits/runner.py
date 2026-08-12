from collections.abc import Iterator
from importlib import import_module
from inspect import isfunction, signature
from typing import Any

from bits.definitions import BitDefinition
from octopoes.models import OOI


class ModuleException(Exception):
    """General error for modules"""


class BitRunner:
    def __init__(self, bit_definition: BitDefinition):
        self.module = bit_definition.module

    def run(self, *args: Any, **kwargs: Any) -> list[OOI]:
        module = import_module(self.module)

        if not hasattr(module, "run") or not isfunction(module.run):
            raise ModuleException(f"Module {module} does not define a run function")

        if signature(module.run).return_annotation != BIT_SIGNATURE.return_annotation:
            raise ModuleException(
                f"Invalid run function return annotation, expected '{BIT_SIGNATURE.return_annotation}'"
            )
        return list(module.run(*args, **kwargs))

    def __str__(self) -> str:
        return f"BitRunner {self.module}"


def _bit_run_signature(input_ooi: OOI, additional_oois: list[OOI], config: dict[str, Any]) -> Iterator[OOI]:
    yield input_ooi


BIT_SIGNATURE = signature(_bit_run_signature)
