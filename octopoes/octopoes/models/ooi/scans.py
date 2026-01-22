from __future__ import annotations

from typing import Literal

import yaml

from octopoes.models import OOI, Reference


class ExternalScan(OOI):
    object_type: Literal["ExternalScan"] = "ExternalScan"

    name: str

    _natural_key_attrs = ["name"]
    _information_value = ["name"]
    _traversable = False

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return reference.tokenized.name

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: ExternalScan) -> yaml.Node:
        return dumper.represent_mapping("!ExternalScan", {**cls.get_ooi_yml_repr_dict(data), "name": data.name})
