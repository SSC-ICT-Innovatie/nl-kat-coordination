import json
import re
from collections.abc import Iterable
from ipaddress import IPv4Address, IPv6Address

from dns.message import Message, from_text
from dns.rdtypes.ANY.CAA import CAA
from dns.rdtypes.ANY.CNAME import CNAME
from dns.rdtypes.ANY.MX import MX
from dns.rdtypes.ANY.NS import NS
from dns.rdtypes.ANY.SOA import SOA
from dns.rdtypes.ANY.TXT import TXT
from dns.rdtypes.IN.A import A
from dns.rdtypes.IN.AAAA import AAAA

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.dns.records import (
    NXDOMAIN,
    DNSAAAARecord,
    DNSARecord,
    DNSCAARecord,
    DNSCNAMERecord,
    DNSMXRecord,
    DNSNSRecord,
    DNSRecord,
    DNSSOARecord,
    DNSTXTRecord,
)
from octopoes.models.ooi.dns.zone import DNSZone, Hostname
from octopoes.models.ooi.email_security import DKIMExists, DMARCTXTRecord
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, Network


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    internet = Network(name="internet")

    if raw.decode() == "NXDOMAIN":
        yield NXDOMAIN(hostname=Reference.from_str(input_ooi["primary_key"]))
        return

    results = json.loads(raw)

    # parse raw data into dns.response.Message
    sections = results["dns_records"].split("\n\n")
    responses: list[Message] = []
    for section in sections:
        lines = section.split("\n")
        responses.append(from_text("\n".join(lines[1:])))

    zone = None
    hostname_store: dict[str, Hostname] = {}
    record_store: dict[str, DNSRecord] = {}

    def register_hostname(name: str) -> Hostname:
        hostname = Hostname(network=internet.reference, name=name.rstrip("."))
        hostname_store[hostname.name] = hostname
        return hostname

    def register_record(record: DNSRecord) -> DNSRecord:
        record_store[record.reference] = record
        return record

    # register argument hostname
    input_hostname = register_hostname(input_ooi["name"])

    # keep track of discovered zones
    zone_links: dict[str, DNSZone] = {}

    for response in responses:
        for rrset in response.answer:
            for rr in rrset:
                record_hostname = register_hostname(str(rrset.name))
                default_args = {"hostname": record_hostname.reference, "value": str(rr), "ttl": rrset.ttl}

                # the soa is the zone of itself, and the argument hostname
                if isinstance(rr, SOA):
                    zone = DNSZone(hostname=record_hostname.reference)
                    zone_links[record_hostname.name] = zone
                    zone_links[input_hostname.name] = zone

                    soa = DNSSOARecord(
                        serial=rr.serial,
                        refresh=rr.refresh,
                        retry=rr.retry,
                        expire=rr.expire,
                        minimum=rr.minimum,
                        soa_hostname=register_hostname(str(rr.mname)).reference,
                        **default_args,
                    )
                    yield soa

                if isinstance(rr, A):
                    ipv4 = IPAddressV4(network=internet.reference, address=IPv4Address(str(rr)))
                    yield ipv4
                    register_record(DNSARecord(address=ipv4.reference, **default_args))

                if isinstance(rr, AAAA):
                    ipv6 = IPAddressV6(network=internet.reference, address=IPv6Address(str(rr)))
                    yield ipv6
                    register_record(DNSAAAARecord(address=ipv6.reference, **default_args))

                if isinstance(rr, TXT):
                    # TODO: concatenated txt records should be handled better
                    # see https://www.rfc-editor.org/rfc/rfc1035 3.3.14
                    default_args["value"] = str(rr).strip('"').replace('" "', "")
                    register_record(DNSTXTRecord(**default_args))

                if isinstance(rr, MX):
                    mail_hostname_reference = None
                    if str(rr.exchange) != ".":
                        mail_fqdn = register_hostname(str(rr.exchange))
                        mail_hostname_reference = mail_fqdn.reference

                    register_record(
                        DNSMXRecord(mail_hostname=mail_hostname_reference, preference=rr.preference, **default_args)
                    )

                if isinstance(rr, NS):
                    ns_fqdn = register_hostname(str(rr.target))
                    register_record(DNSNSRecord(name_server_hostname=ns_fqdn.reference, **default_args))

                if isinstance(rr, CNAME):
                    target_fqdn = register_hostname(str(rr.target))
                    register_record(DNSCNAMERecord(target_hostname=target_fqdn.reference, **default_args))

                if isinstance(rr, CAA):
                    record_value = str(rr).split(" ", 2)
                    default_args["flags"] = min(max(0, int(record_value[0])), 255)
                    default_args["tag"] = re.sub("[^\\w]", "", record_value[1].lower())
                    default_args["value"] = record_value[2]
                    register_record(DNSCAARecord(**default_args))

    # link the hostnames to their discovered zones
    for hostname_, zone in zone_links.items():
        hostname_store[hostname_].dns_zone = zone.reference

    if zone:
        yield zone
    yield from hostname_store.values()
    yield from record_store.values()

    # DKIM
    dkim_results = results["dkim_response"]
    if dkim_results not in ["NXDOMAIN", "Timeout", "DNSSECFAIL"] and dkim_results.split("\n")[2] == "rcode NOERROR":
        yield DKIMExists(hostname=input_hostname.reference)

    # DMARC
    dmarc_results = results["dmarc_response"]
    if dmarc_results not in ["NXDOMAIN", "Timeout"]:
        for rrset in from_text(dmarc_results).answer:
            for rr in rrset:
                if isinstance(rr, TXT):
                    yield DMARCTXTRecord(hostname=input_hostname.reference, value=str(rr).strip('"'), ttl=rrset.ttl)
