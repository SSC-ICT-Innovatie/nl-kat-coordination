import json
import logging
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.network import Network
from octopoes.models.ooi.web import URL

logger = logging.getLogger(__name__)


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    hostname_reference = Reference.from_str(input_ooi["primary_key"])
    network = Network(name=hostname_reference.tokenized.network.name)
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

        kft = KATFindingType(id="EXPOSED-ADMIN-PANELS")
        yield kft

        # Attach each detection to the exact URL nuclei matched. Otherwise every
        # panel on the same host shares the natural key f"{hostname}|{finding_type}"
        # and all detections collapse into a single Finding. Fall back to the
        # hostname when nuclei reports no usable match location.
        finding_ooi = hostname_reference
        matched_at = data.get("matched-at") or data.get("matched_at")
        if matched_at:
            try:
                url = URL(network=network.reference, raw=matched_at)
                yield url
                finding_ooi = url.reference
            except ValueError:
                logger.warning("Could not parse nuclei matched-at %r as a URL", matched_at)

        yield Finding(
            finding_type=kft.reference,
            ooi=finding_ooi,
            proof=data.get("curl-command"),
            description=data.get("info", {}).get("description"),
            reproduce=None,
        )
