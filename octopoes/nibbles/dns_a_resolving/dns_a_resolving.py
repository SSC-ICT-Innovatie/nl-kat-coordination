from collections.abc import Iterator

from octopoes.models import OOI
from octopoes.models.ooi.dns.records import DNSARecord
from octopoes.models.ooi.dns.zone import ResolvedHostname


def nibble(dns_a_record: DNSARecord) -> Iterator[OOI]:
    yield ResolvedHostname(hostname=dns_a_record.hostname, address=dns_a_record.address)
