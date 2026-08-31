from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import CSPDirective, CSPSource, HTTPHeader


def run(input_ooi: HTTPHeader, additional_oois: list, config: dict[str, Any]) -> Iterator[OOI]:
    """Parse a Content-Security-Policy header into structured CSPDirective/CSPSource OOIs.

    Directives are ';'-separated and the tokens within a directive are whitespace-separated. Parsing
    is done with plain string operations (no backtracking regex), so a hostile header cannot cause the
    ReDoS the previous regex-based checker suffered from. Syntactic problems are flagged as a finding
    against the supplying header; semantic/policy compliance is left to a separate policy bit.
    """
    if input_ooi.key.lower() != "content-security-policy":
        return

    findings: list[str] = []
    seen_directives: set[str] = set()

    raw_directives = [directive.strip() for directive in input_ooi.value.split(";")]
    if not any(raw_directives):
        findings.append("CSP header is empty.")

    for raw_directive in raw_directives:
        if not raw_directive:
            continue

        tokens = raw_directive.split()
        name = tokens[0].lower()
        sources = tokens[1:]

        if name in seen_directives:
            findings.append(f"Duplicate CSP directive: {name}")
            continue
        seen_directives.add(name)

        directive = CSPDirective(header=input_ooi.reference, name=name)
        yield directive

        if not sources:
            findings.append(f"CSP directive {name} has no value.")

        for source in sources:
            yield CSPSource(directive=directive.reference, value=source)

    if findings:
        description = "List of CSP parsing issues:\n" + "\n".join(
            f" {index + 1}. {finding}" for index, finding in enumerate(findings)
        )
        # A dedicated finding type, so these syntactic findings don't share a primary key with the
        # policy findings that check-csp-policy emits on the same header (which would clobber each other).
        finding_type = KATFindingType(id="KAT-CSP-INVALID")
        yield finding_type
        yield Finding(finding_type=finding_type.reference, ooi=input_ooi.reference, description=description)
