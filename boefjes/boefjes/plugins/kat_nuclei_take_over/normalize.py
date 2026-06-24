import json
import logging
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType

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
            logger.warning("Skipping non-JSON line in nuclei output")
            continue

        kft = KATFindingType(id="SUB-DOMAIN-TAKEOVER")
        yield kft

        yield Finding(
            finding_type=kft.reference,
            ooi=url_reference,
            proof=data.get("curl-command"),
            description=data.get("info", {}).get("name"),
            reproduce=None,
        )
