from collections.abc import Iterable

import defusedxml.ElementTree as ET

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    """Parse sslscan XML into protocol-version findings, bound to the input
    (HostnameIPService or IPService): protocol support is a property of the
    service, per client capability variant."""
    root = ET.fromstring(raw)
    endpoint_reference = Reference.from_str(input_ooi["primary_key"])

    protocols = []
    for protocol in root.findall("./ssltest/protocol"):
        type_ = protocol.attrib["type"]
        version = protocol.attrib["version"]
        enabled = protocol.attrib["enabled"] == "1"

        protocols.append((type_, version, enabled))

    if not any(protocol[2] for protocol in protocols):
        # No protocol is enabled. This happens when the handshake fails —
        # e.g. a server name the service does not know. Not a false
        # positive, not a finding.
        return

    findings_target = endpoint_reference
    if ("ssl", "2", True) in protocols:
        kft = KATFindingType(id="KAT-SSL-2-SUPPORT")
        yield kft
        yield Finding(finding_type=kft.reference, ooi=findings_target)
    elif ("ssl", "3", True) in protocols:
        kft = KATFindingType(id="KAT-SSL-3-SUPPORT")
        yield kft
        yield Finding(finding_type=kft.reference, ooi=findings_target)
    elif ("tls", "1.0", True) in protocols and ("tls", "1.1", False) in protocols:
        kft = KATFindingType(id="KAT-TLS-1.0-SUPPORT")
        yield kft
        yield Finding(finding_type=kft.reference, ooi=findings_target)
    elif ("tls", "1.1", True) in protocols and ("tls", "1.0", False) in protocols:
        kft = KATFindingType(id="KAT-TLS-1.1-SUPPORT")
        yield kft
        yield Finding(finding_type=kft.reference, ooi=findings_target)
    elif ("tls", "1.0", True) in protocols and ("tls", "1.1", True) in protocols:
        kft = KATFindingType(id="KAT-TLS-1.0-AND-1.1-SUPPORT")
        yield kft
        yield Finding(finding_type=kft.reference, ooi=findings_target)
    elif ("tls", "1.2", False) in protocols:
        kft = KATFindingType(id="KAT-NO-TLS-1.2")
        yield kft
        yield Finding(finding_type=kft.reference, ooi=findings_target)
    elif ("tls", "1.3", False) in protocols:
        kft = KATFindingType(id="KAT-NO-TLS-1.3")
        yield kft
        yield Finding(finding_type=kft.reference, ooi=findings_target)

    fallback = root.find("./ssltest/fallback")
    if fallback is not None and fallback.attrib["supported"] != "1":
        kft = KATFindingType(id="KAT-NO-TLS-FALLBACK-SCSV")
        yield kft
        yield Finding(finding_type=kft.reference, ooi=findings_target)
