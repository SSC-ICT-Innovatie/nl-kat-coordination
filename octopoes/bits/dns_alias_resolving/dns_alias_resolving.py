from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.dns.records import DNSCNAMERecord
from octopoes.models.ooi.dns.zone import Hostname, ResolvedHostname
from octopoes.models.ooi.network import Network


def run(
    hostname: Hostname, additional_oois: list[DNSCNAMERecord | ResolvedHostname], config: dict[str, Any]
) -> Iterator[OOI]:
    cname_records = [ooi for ooi in additional_oois if isinstance(ooi, DNSCNAMERecord)]
    resolved_hostnames = [ooi for ooi in additional_oois if isinstance(ooi, ResolvedHostname)]

    for cname_record in cname_records:
        for resolved_hostname in resolved_hostnames:
            yield ResolvedHostname(hostname=cname_record.hostname, address=resolved_hostname.address)
            # Also the non-fqdn variant
            yield ResolvedHostname(
                hostname=Hostname(
                    name=cname_record.hostname.tokenized.name,
                    network=Network(name=cname_record.hostname.tokenized.network.name).reference,
                ).reference,
                address=resolved_hostname.address,
            )
