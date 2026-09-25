import csv
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.service import TLSCipher

SEVERITY_TO_ID = {
    "Critical": "KAT-CRITICAL-TLS-CIPHER",
    "High": "KAT-HIGH-TLS-CIPHER",
    "Medium": "KAT-MEDIUM-TLS-CIPHER",
    "Low": "KAT-LOW-TLS-CIPHER",
    "Recommendation": "KAT-RECOMMENDATION-TLS-CIPHER",
}

SEVERITY_LEVELS = {"Critical": 5, "High": 4, "Medium": 3, "Low": 2, "Recommendation": 1, "Informational": 0}


def get_severity_and_reasons(cipher_suite: str) -> list[tuple[str, str]]:
    with Path.open(Path(__file__).parent / "tls-cipher-findings.csv", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        data = [{k.strip(): v.strip() for k, v in row.items() if k} for row in reader]

    # Filter the data for the provided cipher suite
    cipher_suite_data = [row for row in data if row["Cipher suite"] == cipher_suite]

    # If the cipher suite is not found, return an empty list
    if not cipher_suite_data:
        return [("Recommendation", "Unknown cipher")]

    # Columns that contain severities
    severity_cols = [col for col in data[0] if "Severity" in col]

    # Columns that contain reasons
    reason_cols = [col for col in data[0] if "Title" in col]

    severities_and_reasons = []
    for row in cipher_suite_data:
        for severity_col, reason_col in zip(severity_cols, reason_cols):
            # Check if there's a severity rating and a reason in the row
            if row[severity_col] and row[reason_col]:
                # Append the severity and reason as a tuple to the list
                severities_and_reasons.append(
                    (row[severity_col], f"{cipher_suite} - {row[reason_col]} ({row[severity_col]}).")
                )
    return severities_and_reasons


def get_reasons_by_severity(cipher_suites: dict) -> dict[str, list[str]]:
    reasons_by_severity: dict[str, list[str]] = {}

    for suites in cipher_suites.values():
        for suite in suites:
            cipher_suite = suite["cipher_suite_name"]

            for severity, reason in get_severity_and_reasons(cipher_suite):
                reasons_by_severity.setdefault(severity, []).append(reason)

    return reasons_by_severity


def run(input_ooi: TLSCipher, additional_oois: list, config: dict[str, Any]) -> Iterator[OOI]:
    reasons_by_severity = get_reasons_by_severity(input_ooi.suites)

    for severity in sorted(reasons_by_severity, key=lambda severity: SEVERITY_LEVELS.get(severity, -1), reverse=True):
        if severity not in SEVERITY_TO_ID:
            continue

        ft = KATFindingType(id=SEVERITY_TO_ID[severity])
        yield ft

        yield Finding(
            finding_type=ft.reference,
            ooi=input_ooi.reference,
            description=(
                "One or more of the cipher suites should not be used because:\n"
                + "\n".join(reasons_by_severity[severity])
            ),
        )
