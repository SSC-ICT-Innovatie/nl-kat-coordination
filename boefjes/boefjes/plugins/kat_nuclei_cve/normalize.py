import json
import logging
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import CVEFindingType, Finding

logger = logging.getLogger(__name__)


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    url_reference = Reference.from_str(input_ooi["primary_key"])
    if not raw:
        return

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            # A single malformed line must not abort the whole task.
            logger.warning("Skipping non-JSON line in nuclei output")
            continue

        # A nuclei result only maps to a CVE finding when it carries a cve-id.
        # Templates without one (e.g. CWE-only classifications) are skipped, not crashed on.
        cve_ids = (data.get("info", {}).get("classification") or {}).get("cve-id") or []
        if not cve_ids:
            continue

        cve_finding_type = CVEFindingType(id=str(cve_ids[0]).upper())
        yield cve_finding_type

        # description and curl-command are optional in nuclei output.
        yield Finding(
            finding_type=cve_finding_type.reference,
            ooi=url_reference,
            proof=data.get("curl-command"),
            description=data.get("info", {}).get("description"),
            reproduce=None,
        )
