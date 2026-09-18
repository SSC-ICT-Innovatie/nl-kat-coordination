import re
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import SecurityTXT

# RFC 9116 field names (case-insensitive)
REQUIRED_FIELDS = {"contact", "expires"}
RECOMMENDED_FIELDS = {"encryption"}
OPTIONAL_FIELDS = {"acknowledgments", "canonical", "policy", "hiring", "preferred-languages"}
KNOWN_FIELDS = REQUIRED_FIELDS | RECOMMENDED_FIELDS | OPTIONAL_FIELDS

# Expires format: ISO 8601, e.g. 2024-12-31T23:59:59.000Z
EXPIRES_RE = re.compile(r"^Expires:\s*(.+)$", re.MULTILINE | re.IGNORECASE)


def run(input_ooi: SecurityTXT, additional_oois: list, config: dict[str, Any]) -> Iterator[OOI]:
    """Validate a security.txt file against RFC 9116.

    Checks for required fields (Contact, Expires), expired Expires dates,
    and missing recommended fields (Encryption). Unknown fields are ignored
    per RFC 9116 §2.2.
    """
    content = input_ooi.security_txt
    if not content:
        return

    fields = _parse_fields(content)
    issues: list[str] = []

    # Required fields
    for field in REQUIRED_FIELDS:
        if field not in fields:
            issues.append(f"Required field '{field.capitalize()}' is missing")

    # Expires date validation
    if "expires" in fields:
        expires_str = fields["expires"]
        try:
            # Accept both with and without timezone suffix
            expires_dt = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            if expires_dt < datetime.now(timezone.utc):
                issues.append(f"Expires date ({expires_str}) is in the past")
        except ValueError:
            issues.append(f"Expires date '{expires_str}' is not a valid ISO 8601 date")

    # Recommended fields (informational — not required by RFC 9116)
    for field in RECOMMENDED_FIELDS:
        if field not in fields:
            issues.append(f"Recommended field '{field.capitalize()}' is missing")

    if issues:
        description = "security.txt validation issues:\n" + "\n".join(f"  - {issue}" for issue in issues)
        ft = KATFindingType(id="KAT-INVALID-SECURITY-TXT")
        yield ft
        yield Finding(finding_type=ft.reference, ooi=input_ooi.reference, description=description)


def _parse_fields(content: str) -> dict[str, str]:
    """Parse security.txt content into a dict of field_name -> value.

    Handles multi-line values (continuation lines per RFC 9116 §2.2.3) and
    signed files (PGP blocks are skipped).
    """
    # Skip PGP signature blocks — only parse the unsigned portion
    if "-----BEGIN PGP" in content:
        content = _strip_pgp_block(content)

    fields: dict[str, str] = {}
    current_key: str | None = None
    current_value: list[str] = []

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            # Flush current field on blank line or comment
            if current_key:
                fields[current_key] = " ".join(current_value).strip()
                current_key = None
                current_value = []
            continue

        if ":" in line:
            # Flush previous field
            if current_key:
                fields[current_key] = " ".join(current_value).strip()
            key, _, value = line.partition(":")
            current_key = key.strip().lower()
            current_value = [value.strip()]
        elif current_key:
            # Continuation line
            current_value.append(line)

    # Flush last field
    if current_key:
        fields[current_key] = " ".join(current_value).strip()

    return fields


def _strip_pgp_block(content: str) -> str:
    """Remove PGP signature block, keeping only the signed content."""
    lines = content.splitlines()
    result: list[str] = []
    in_pgp = False
    for line in lines:
        if "-----BEGIN PGP" in line:
            in_pgp = True
            continue
        if "-----END PGP" in line:
            in_pgp = False
            continue
        if not in_pgp:
            result.append(line)
    return "\n".join(result)
