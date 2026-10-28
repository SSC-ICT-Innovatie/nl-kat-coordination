import json
from pathlib import Path

import pytest

from boefjes.plugins.kat_kat_finding_types.validate_groups import validate_groups

CATALOG_DIR = Path(__file__).resolve().parents[2] / "boefjes/plugins/kat_kat_finding_types"


def test_catalog_group_assignments():
    registry = json.loads((CATALOG_DIR / "finding_type_groups.json").read_text())
    catalog = json.loads((CATALOG_DIR / "kat_finding_types.json").read_text())
    # Tripwire for accidental registry removals; routine additions are fine.
    assert len(registry) == 18
    # Every finding type must carry at least one known, duplicate-free group.
    for identifier, entry in catalog.items():
        assert entry.get("groups"), f"{identifier} has no groups"
        assert all(group in registry for group in entry["groups"]), f"{identifier} references unknown groups"
    validate_groups(registry, catalog)
    assert "http-security-headers" in catalog["KAT-NO-HSTS"]["groups"]
    assert "http-cookies" in catalog["KAT-INSECURE-COOKIE"]["groups"]


@pytest.mark.parametrize("parent", ["missing", "web-security"])
def test_invalid_parent(parent):
    registry = {"web-security": {"name": "Web", "description": "Web security", "parent": parent}}
    with pytest.raises(ValueError):
        validate_groups(registry, {})


def test_invalid_assignment():
    registry = {"web-security": {"name": "Web", "description": "Web security", "parent": None}}
    with pytest.raises(ValueError):
        validate_groups(registry, {"KAT-EXAMPLE": {"groups": ["unknown"]}})


def test_catalog_optional_misconfiguration_tags():
    catalog = json.loads((CATALOG_DIR / "kat_finding_types.json").read_text())

    tagged = [identifier for identifier, entry in catalog.items() if "misconfiguration" in entry.get("tags", [])]
    assert tagged, "expected at least one misconfiguration-tagged finding type"
    assert catalog["KAT-NO-DNSSEC"]["tags"] == ["misconfiguration"]
    assert catalog["KAT-INSECURE-COOKIE"]["tags"] == ["misconfiguration"]
    assert "tags" not in catalog["KAT-LEAKIX-MEDIUM"]


@pytest.mark.parametrize("tags", ["misconfiguration", [""], [1], ["misconfiguration", "misconfiguration"], None])
def test_invalid_tags(tags):
    registry = {"dns-security": {"name": "DNS", "description": "DNS security", "parent": None}}
    with pytest.raises(ValueError, match="Invalid tags"):
        validate_groups(registry, {"KAT-EXAMPLE": {"groups": ["dns-security"], "tags": tags}})


def test_optional_tags_are_valid():
    registry = {"dns-security": {"name": "DNS", "description": "DNS security", "parent": None}}
    validate_groups(registry, {"KAT-EXAMPLE": {"groups": ["dns-security"]}})
    validate_groups(registry, {"KAT-EXAMPLE": {"groups": ["dns-security"], "tags": []}})
    validate_groups(registry, {"KAT-EXAMPLE": {"groups": ["dns-security"], "tags": ["misconfiguration", "custom"]}})
