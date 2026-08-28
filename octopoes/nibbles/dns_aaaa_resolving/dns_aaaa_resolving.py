from collections.abc import Iterator

from octopoes.models import OOI
from octopoes.models.ooi.dns.records import DNSAAAARecord
from octopoes.models.ooi.dns.zone import ResolvedHostname


def nibble(dns_aaaa_record: DNSAAAARecord) -> Iterator[OOI]:
    yield ResolvedHostname(hostname=dns_aaaa_record.hostname, address=dns_aaaa_record.address)
