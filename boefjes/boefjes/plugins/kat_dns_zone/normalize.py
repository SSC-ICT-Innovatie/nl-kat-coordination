from collections.abc import Iterable

from dns.message import Message, from_text
from dns.rdtypes.ANY.SOA import SOA

from boefjes.normalizer_models import NormalizerAffirmation, NormalizerOutput
from octopoes.models.ooi.dns.records import DNSSOARecord
from octopoes.models.ooi.dns.zone import DNSZone, Hostname
from octopoes.models.ooi.network import Network


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    name = input_ooi["hostname"]["name"] if "hostname" in input_ooi else input_ooi["name"]
    networkname = input_ooi["hostname"]["network"]["name"] if "hostname" in input_ooi else input_ooi["network"]["name"]
    network = Network(name=networkname)

    # parse raw data into dns.message.Message
    section = raw.decode()
    lines = section.split("\n")
    message: Message = from_text("\n".join(lines[1:]))

    input_zone_hostname = Hostname(network=network.reference, name=input_ooi["hostname"]["name"])

    input_zone = DNSZone(hostname=input_zone_hostname.reference)

    for rrset in message.answer:
        for rr in rrset:
            if isinstance(rr, SOA):
                parent_zone_hostname = None
                if str(rrset.name).rstrip(".") != "":
                    parent_zone_hostname = Hostname(network=network.reference, name=str(rrset.name).rstrip("."))
                    parent_zone = DNSZone(hostname=parent_zone_hostname.reference)
                    parent_zone_hostname.dns_zone = parent_zone.reference
                    yield parent_zone_hostname
                    yield parent_zone

                soa_hostname = None
                if str(rr.mname).rstrip(".") != "":
                    soa_hostname = Hostname(network=network.reference, name=str(rr.mname).rstrip("."))
                    yield soa_hostname

                yield DNSSOARecord(
                    hostname=parent_zone_hostname.reference if parent_zone_hostname else "",
                    value=str(rr),
                    ttl=rrset.ttl,
                    soa_hostname=soa_hostname.reference if soa_hostname else "",
                    serial=rr.serial,
                    retry=rr.retry,
                    refresh=rr.refresh,
                    expire=rr.expire,
                    minimum=rr.minimum,
                )

                if str(name).rstrip(".") != "":
                    if "hostname" in input_ooi:
                        # lets yield the dnszone again as a affirmation, adding only the dnszone property
                        input_zone_hostname = Hostname(network=network.reference, name=str(name).rstrip("."))
                        input_zone = DNSZone(hostname=input_zone_hostname.reference, parent=parent_zone.reference)
                        yield NormalizerAffirmation(ooi=input_zone)
                    else:
                        # lets yield the hostname again as a affirmation, adding only the dnszone property
                        hostname_ooi = Hostname(network=network.reference, name=str(name).rstrip("."))
                        hostname_ooi.dns_zone = parent_zone.reference
                        yield NormalizerAffirmation(ooi=hostname_ooi)
