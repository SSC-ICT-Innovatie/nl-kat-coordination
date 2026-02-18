from collections.abc import Iterable

import defusedxml.ElementTree as ET

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    root = ET.fromstring(raw)
    website_reference = Reference.from_str(input_ooi["primary_key"])

    protocols = []
    for protocol in root.findall("./ssltest/protocol"):
        type_ = protocol.attrib["type"]
        version = protocol.attrib["version"]
        enabled = protocol.attrib["enabled"] == "1"

        protocols.append((type_, version, enabled))

    if not any(protocol[2] for protocol in protocols):
        # No protocol is enabled. This might happen if we send a hostname that
        # is not configured for TLS. We shouldn't create a false positive
        # finding for this.
        return

    if ("ssl", "2", True) in protocols:
        kft = KATFindingType(id="KAT-SSL-2-SUPPORT")
        yield kft
        yield Finding(finding_type=kft.reference, ooi=website_reference)
    elif ("ssl", "3", True) in protocols:
        kft = KATFindingType(id="KAT-SSL-3-SUPPORT")
        yield kft
        yield Finding(finding_type=kft.reference, ooi=website_reference)
    elif ("tls", "1.0", True) in protocols and ("tls", "1.1", False) in protocols:
        kft = KATFindingType(id="KAT-TLS-1.0-SUPPORT")
        yield kft
        yield Finding(finding_type=kft.reference, ooi=website_reference)
    elif ("tls", "1.1", True) in protocols and ("tls", "1.0", False) in protocols:
        kft = KATFindingType(id="KAT-TLS-1.1-SUPPORT")
        yield kft
        yield Finding(finding_type=kft.reference, ooi=website_reference)
    elif ("tls", "1.0", True) in protocols and ("tls", "1.1", True) in protocols:
        kft = KATFindingType(id="KAT-TLS-1.0-AND-1.1-SUPPORT")
        yield kft
        yield Finding(finding_type=kft.reference, ooi=website_reference)
    elif ("tls", "1.2", False) in protocols:
        kft = KATFindingType(id="KAT-NO-TLS-1.2")
        yield kft
        yield Finding(finding_type=kft.reference, ooi=website_reference)
    elif ("tls", "1.3", False) in protocols:
        kft = KATFindingType(id="KAT-NO-TLS-1.3")
        yield kft
        yield Finding(finding_type=kft.reference, ooi=website_reference)

    fallback = root.find("./ssltest/fallback")
    if fallback is not None and fallback.attrib["supported"] != "1":
        kft = KATFindingType(id="KAT-NO-TLS-FALLBACK-SCSV")
        yield kft
        yield Finding(finding_type=kft.reference, ooi=website_reference)
