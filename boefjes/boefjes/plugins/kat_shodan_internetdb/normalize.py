import json
import logging
from collections.abc import Iterable

from boefjes.plugins.helpers import cpe_to_name_version
from octopoes.models import OOI, Reference
from octopoes.models.ooi.dns.records import DNSPTRRecord
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import CVEFindingType, Finding
from octopoes.models.ooi.network import IPPort, Network, PortState, Protocol
from octopoes.models.ooi.software import Software, SoftwareInstance

DNS_PTR_STR = ".in-addr.arpa"


def run(input_ooi: dict, raw: bytes) -> Iterable[OOI]:
    """Normalize InternetDB output."""
    result = json.loads(raw)
    input_ooi_reference = Reference.from_str(input_ooi["primary_key"])
    input_ooi_str = input_ooi["address"]

    if not result:
        logging.info("No InternetDB results available for normalization.")
    elif "detail" in result:
        if result["detail"] == "No information available":
            logging.info("No information available for IP.")
        else:
            logging.warning("Unexpected detail: %s", result["detail"])
    else:
        # Previously the "cdn" tag short-circuited everything: hostnames, vulns,
        # ports and every non-Cloudflare cpe were skipped. Always process the
        # full result; the CDN provider is recorded as Software via its cpe like
        # any other software.
        for hostname in result.get("hostnames", []):
            hostname_ooi = Hostname(name=hostname, network=Network(name=input_ooi["network"]["name"]).reference)
            yield hostname_ooi
            if hostname.endswith(DNS_PTR_STR):
                yield DNSPTRRecord(hostname=hostname_ooi.reference, value=hostname, address=input_ooi_reference)

        # InternetDB does not distinguish transport, so TCP is assumed.
        for port in result.get("ports", []):
            yield IPPort(address=input_ooi_reference, protocol=Protocol.TCP, port=int(port), state=PortState("open"))

        for cve in result.get("vulns", []):
            finding_type = CVEFindingType(id=cve)
            finding = Finding(
                finding_type=finding_type.reference,
                ooi=input_ooi_reference,
                proof=f"https://internetdb.shodan.io/{input_ooi_str}",
            )
            yield finding_type
            yield finding

        for cpe in result.get("cpes", []):
            name, version = cpe_to_name_version(cpe=cpe)
            software = Software(name=name, version=version, cpe=cpe)
            yield software
            yield SoftwareInstance(software=software.reference, ooi=input_ooi_reference)
