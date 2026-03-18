from collections.abc import Sequence
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from django.contrib.auth import get_user_model
from pydantic import TypeAdapter

from octopoes.api.models import Declaration
from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models import OOI
from octopoes.models.exception import ObjectNotFoundException
from octopoes.models.ooi.findings import (
    CAPECFindingType,
    CVEFindingType,
    CWEFindingType,
    Finding,
    FindingType,
    KATFindingType,
    RetireJSFindingType,
    SnykFindingType,
)
from octopoes.models.tree import ReferenceNode
from octopoes.models.types import OOI_TYPES, get_relations
from rocky.bytes_client import BytesClient
from tools.models import OOIInformation

User = get_user_model()

RISK_LEVEL_SCORE_DEFAULT = 10


def format_attr_name(s: str) -> str:
    return s.replace("_", " ").replace("/", " -> ").title()


def format_value(value: Any) -> str:
    if isinstance(value, Enum):
        return value.value
    return value


def format_display(data: dict, ignore: list | None = None) -> dict[str, str]:
    if ignore is None:
        ignore = []

    return {format_attr_name(k): format_value(v) for k, v in data.items() if k not in ignore}


def get_knowledge_base_data_for_ooi_store(ooi_store: dict) -> dict[str, dict]:
    knowledge_base = {}

    for ooi in ooi_store.values():
        # build knowledge base
        if ooi.get_information_id() not in knowledge_base:
            knowledge_base[ooi.get_information_id()] = get_knowledge_base_data_for_ooi(ooi)

    return knowledge_base


def get_knowledge_base_data_for_ooi(ooi: OOI) -> dict:
    knowledge_base_data = {}

    # Knowledge base data
    information_id = ooi.get_information_id()
    if information_id != ooi.get_ooi_type():
        info, created = OOIInformation.objects.get_or_create(id=information_id)
        if info.description:
            knowledge_base_data.update(info.data)

    try:
        info_on_type = OOIInformation.objects.get(id=ooi.get_ooi_type())
        knowledge_base_data["Information"] = info_on_type.description
    except OOIInformation.DoesNotExist:
        pass

    return knowledge_base_data


def process_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, int | float):
        return value
    return str(value) if value else None


def get_ooi_dict(ooi: OOI) -> dict:
    ooi_dict = {"id": ooi.primary_key, "ooi_type": ooi.get_ooi_type(), "human_readable": ooi.human_readable}

    ignore_properties = ["primary_key", "scan_profile"]

    # Props are everything but refs
    relations = get_relations(ooi.__class__)
    for attr_name, value in ooi:
        if attr_name not in relations and attr_name not in ignore_properties:
            ooi_dict[attr_name] = process_value(value)

    return ooi_dict


def get_tree_meta(tree_node: dict, depth: int, location: str) -> dict:
    tree_meta: dict[str, Any] = {
        "depth": depth,
        "location": location,
        "child_count": "0",  # TO_DO ? child_count doesn't exist in template if not a string
        "has_findings": False,
        "has_jobs": False,
    }

    if "children" in tree_node:
        tree_meta["child_count"] = str(len(tree_node["children"]))
        tree_meta["child_ids"] = [child["id"] for child in tree_node["children"]]
        tree_meta["child_ooi_types"] = [child["ooi_type"] for child in tree_node["children"]]

        for ooi_type in tree_meta["child_ooi_types"]:
            if ooi_type in ["Finding"]:
                tree_meta["has_findings"] = True
            if ooi_type == "Job":
                tree_meta["has_jobs"] = True

    return tree_meta


def create_object_tree_item_from_ref(
    reference_node: ReferenceNode,
    ooi_store: dict[str, OOI],
    knowledge_base: dict[str, dict] | None = None,
    depth: int = 0,
    position: int = 1,
    location: str = "loc",
) -> dict:
    depth = sum([depth, 1])
    location = location + "-" + str(position)

    ooi = ooi_store[str(reference_node.reference)]

    item = get_ooi_dict(ooi)

    if not knowledge_base:
        knowledge_base = get_knowledge_base_data_for_ooi_store(ooi_store)

    if knowledge_base[ooi.get_information_id()]:
        item.update(knowledge_base[ooi.get_information_id()])

    children = []
    child_position = 0
    for relation_name, child_items in reference_node.children.items():
        for child in child_items:
            if not child.reference.class_type.traversable():
                continue
            if child.reference == reference_node.reference:
                continue
            child_position = child_position + 1
            children.append(
                create_object_tree_item_from_ref(child, ooi_store, knowledge_base, depth, child_position, location)
            )

    if children:
        item["children"] = children

    item["tree_meta"] = get_tree_meta(item, depth, location)

    return item


def get_ooi_types_from_tree(ooi, include_self=True):
    types = set()

    for child in ooi.get("children", []):
        for child_type in get_ooi_types_from_tree(child):
            types.add(child_type)

    if include_self and ooi["ooi_type"] not in types:
        types.add(ooi["ooi_type"])

    return sorted(types)


def filter_ooi_tree(ooi_node: dict, show_types: Sequence = [], hide_types: Sequence = []) -> dict:
    if not show_types and not hide_types:
        return ooi_node

    res = filter_ooi_tree_item(ooi_node, show_types, hide_types, True)

    return res[0]


def filter_ooi_tree_item(ooi_node, show_types, hide_types, self_excluded_from_filter=False):
    def include_type(ooi_type):
        # hiding type takes precedence over showing type
        if hide_types and ooi_type in hide_types:
            return False

        if show_types:
            return ooi_type in show_types

        return True

    children = []

    if "children" in ooi_node:
        for child_ooi_node in ooi_node.get("children", []):
            children.extend(filter_ooi_tree_item(child_ooi_node, show_types, hide_types))

        # no duplicates
        child_ids = set()
        ooi_node["children"] = []
        for child in children:
            if child.get("id") not in child_ids and child.get("id") != ooi_node["id"]:
                child_ids.add(child.get("id"))
                ooi_node["children"].append(child)

    if not self_excluded_from_filter and not include_type(ooi_node["ooi_type"]):
        return children

    return [ooi_node]


def get_finding_type_from_finding(finding: Finding) -> FindingType:
    return TypeAdapter(
        KATFindingType | CVEFindingType | CWEFindingType | RetireJSFindingType | SnykFindingType | CAPECFindingType
    ).validate_python({"object_type": finding.finding_type.class_, "id": finding.finding_type.natural_key})


_EXCLUDED = [Finding] + FindingType.strict_subclasses()
OOI_TYPES_WITHOUT_FINDINGS = [name for name, cls_ in OOI_TYPES.items() if cls_ not in _EXCLUDED]


def get_or_create_ooi(
    api_connector: OctopoesAPIConnector,
    bytes_client: BytesClient,
    ooi: OOI,
    observed_at: datetime,
    end_valid_time: datetime | None = None,
) -> tuple[OOI, bool]:
    try:
        return api_connector.get(ooi.reference, observed_at), False
    except ObjectNotFoundException:
        create_ooi(api_connector, bytes_client, ooi, observed_at, end_valid_time)
        return ooi, True


def create_ooi(
    api_connector: OctopoesAPIConnector,
    bytes_client: BytesClient,
    ooi: OOI,
    observed_at: datetime,
    end_valid_time: datetime | None = None,
) -> None:
    task_id = uuid4()
    declaration = Declaration(ooi=ooi, valid_time=observed_at, task_id=task_id, end_valid_time=end_valid_time)
    bytes_client.add_manual_proof(task_id, BytesClient.raw_from_declarations([declaration]))

    api_connector.save_declaration(declaration, sync=True)


def create_oois(
    api_connector: OctopoesAPIConnector,
    bytes_client: BytesClient,
    oois: list[OOI],
    observed_at: datetime,
    end_valid_time: datetime | None = None,
) -> None:
    declarations: list[Declaration] = []
    task_id = uuid4()

    for ooi in oois:
        declarations.append(
            Declaration(ooi=ooi, valid_time=observed_at, task_id=task_id, end_valid_time=end_valid_time)
        )

    bytes_client.add_manual_proof(task_id, BytesClient.raw_from_declarations(declarations))
    api_connector.save_many_declarations(declarations, sync=True)
