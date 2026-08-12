from __future__ import annotations

from enum import Enum
from functools import total_ordering
from typing import Annotated, Literal

from pydantic import AnyUrl, StringConstraints

from octopoes.models import OOI, Reference
from octopoes.models.persistence import ReferenceField

severity_order = ["unknown", "pending", "recommendation", "low", "medium", "high", "critical"]


@total_ordering
class RiskLevelSeverity(Enum):
    """Represents the risk level severity of findings

    Possible values
    ---------------
    critical, high, medium, low, recommendation, pending, unknown

    Example value
    -------------
    high
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    RECOMMENDATION = "recommendation"

    # pending = KAT still has to run the boefje to determine the risk level
    PENDING = "pending"

    # unknown = the third party has been contacted, but third party has not determined the risk level (yet)
    UNKNOWN = "unknown"

    def __gt__(self, other: RiskLevelSeverity) -> bool:
        return severity_order.index(self.value) > severity_order.index(other.value)

    def __str__(self) -> str:
        return self.value


class FindingType(OOI):
    """Represents finding types. #TODO: Update once new structure of findings/finding types is complete.

    Possible values
    ---------------
    name, description, source, impact, recommendation, risk_score, risk_severity

    Example value
    -------------
    #TODO once new structure is complete.
    """

    id: str

    name: str | None = None
    description: str | None = None
    source: AnyUrl | None = None
    impact: str | None = None
    recommendation: str | None = None

    risk_score: float | None = None
    risk_severity: RiskLevelSeverity | None = None

    _natural_key_attrs = ["id"]
    _traversable = False

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return reference.tokenized.id


class ADRFindingType(FindingType):
    """Represents the API Design Rules (ADR) Finding Types"""

    object_type: Literal["ADRFindingType"] = "ADRFindingType"


class CVEFindingType(FindingType):
    """Represents the CVE Finding Types"""

    object_type: Literal["CVEFindingType"] = "CVEFindingType"

    id: Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True)]


class CWEFindingType(FindingType):
    """Represents the CWE Finding Types"""

    object_type: Literal["CWEFindingType"] = "CWEFindingType"

    id: Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True)]


class CAPECFindingType(FindingType):
    """Represents the CAPEC Finding Types"""

    object_type: Literal["CAPECFindingType"] = "CAPECFindingType"

    id: Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True)]


class RetireJSFindingType(FindingType):
    """Represents the RetireJS Finding Types"""

    object_type: Literal["RetireJSFindingType"] = "RetireJSFindingType"


class SnykFindingType(FindingType):
    """Represents the Snyk Finding Types"""

    object_type: Literal["SnykFindingType"] = "SnykFindingType"

    id: Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True)]


class KATFindingType(FindingType):
    """Represents the OpenKAT Finding Types"""

    object_type: Literal["KATFindingType"] = "KATFindingType"


class Finding(OOI):
    """Represents all OpenKAT Findings, including CVE's and CWE's.
    #TODO Update once new findings/finding types are complete."""

    object_type: Literal["Finding"] = "Finding"

    finding_type: Reference = ReferenceField(FindingType)
    ooi: Reference = ReferenceField(OOI)
    proof: str | None = None
    description: str | None = None
    reproduce: str | None = None

    @property
    def natural_key(self) -> str:
        return f"{str(self.ooi)}|{self.finding_type.natural_key}"

    _reverse_relation_names = {"ooi": "findings", "finding_type": "instances"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        parts = reference.natural_key.split("|")
        finding_type = parts.pop()
        ooi_reference = Reference.from_str("|".join(parts))
        return f"{finding_type} @ {ooi_reference.human_readable}"


class MutedFinding(OOI):
    """Represents muted findings.

    Muted findings can be attached to findings. This will make the findings not show up on the Findings page.

    Possible values
    ---------------
    finding, reason
    """

    object_type: Literal["MutedFinding"] = "MutedFinding"

    finding: Reference = ReferenceField(Finding)
    reason: str | None = None

    _natural_key_attrs = ["finding"]
    _reverse_relation_names = {"finding": "mutes"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"Muted {reference.natural_key}"
