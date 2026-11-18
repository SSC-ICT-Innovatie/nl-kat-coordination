"""Boefje script for getting dns records"""

import logging
from os import getenv

import dns.resolver
from dns.edns import EDEOption
from dns.name import Name
from dns.resolver import Answer

logger = logging.getLogger(__name__)


class ZoneNotFoundException(Exception):
    pass


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]
    zone_ooi = input_["hostname"]["name"]

    zone_name = dns.name.from_text(zone_ooi)

    zone_parent = zone_name.parent()
    try:
        zone_soa_record = get_parent_zone_soa(zone_parent)
    except dns.resolver.Timeout:
        # The resolvers did not answer in time; not a hard failure.
        return [({"error/timeout"}, f"Resolving the parent zone SOA of {zone_ooi} timed out")]

    answers = [zone_soa_record]
    answers_formatted = [f"RESOLVER: {answer.nameserver}\n{answer.response}" for answer in answers]

    return [(set(), "\n\n".join(answers_formatted))]


def get_parent_zone_soa(name: Name) -> Answer:
    # An explicit resolver (instead of the module-level default) so the
    # nameserver and timeouts are configurable like in the other DNS boefjes.
    # The system resolver (/etc/resolv.conf) is kept as-is unless REMOTE_NS
    # is configured: installs behind an internal resolver or with restricted
    # DNS egress must keep working (per review M3).
    resolver = dns.resolver.Resolver()
    # https://dnspython.readthedocs.io/en/stable/_modules/dns/edns.html
    resolver.use_edns(options=[EDEOption(15)])
    if remote_ns := getenv("REMOTE_NS"):
        resolver.nameservers = [remote_ns]
    # Can be overridden through the plugin settings, see schema.json.
    resolver.timeout = float(getenv("DNS_TIMEOUT", "5"))
    resolver.lifetime = float(getenv("DNS_LIFETIME", "30"))

    while True:
        try:
            return resolver.resolve(name, dns.rdatatype.SOA)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            pass

        try:
            name = name.parent()
        except dns.name.NoParent:
            raise ZoneNotFoundException
