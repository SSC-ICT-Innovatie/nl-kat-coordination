"""Validate the static KAT finding-type group registry and catalog assignments."""

import json
from pathlib import Path

CATALOG_DIR = Path(__file__).resolve().parent


def validate_groups(registry: dict, finding_types: dict) -> None:
    for identifier, group in registry.items():
        if not isinstance(group, dict) or not all(
            isinstance(group.get(field), str) and group[field].strip() for field in ("name", "description")
        ):
            raise ValueError(f"Invalid group definition: {identifier}")
        parent = group.get("parent")
        if parent is not None and (parent not in registry or parent == identifier):
            raise ValueError(f"Invalid parent for group: {identifier}")

    for identifier in registry:
        visited = set()
        current = identifier
        while current is not None:
            if current in visited:
                raise ValueError(f"Cyclic group hierarchy: {identifier}")
            visited.add(current)
            current = registry[current]["parent"]

    for identifier, finding_type in finding_types.items():
        tags = finding_type.get("tags", [])
        if (
            not isinstance(tags, list)
            or any(not isinstance(tag, str) or not tag.strip() for tag in tags)
            or len(tags) != len(set(tags))
        ):
            raise ValueError(f"Invalid tags for finding type: {identifier}")

        groups = finding_type.get("groups")
        if (
            not isinstance(groups, list)
            or not groups
            or any(not isinstance(group, str) or group not in registry for group in groups)
            or len(groups) != len(set(groups))
        ):
            raise ValueError(f"Invalid groups for finding type: {identifier}")


def validate_catalog() -> None:
    registry = json.loads((CATALOG_DIR / "finding_type_groups.json").read_text())
    finding_types = json.loads((CATALOG_DIR / "kat_finding_types.json").read_text())
    validate_groups(registry, finding_types)


if __name__ == "__main__":
    validate_catalog()
