"""Boefje script for getting dns records"""

import logging

import dns.resolver
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
    zone_soa_record = get_parent_zone_soa(zone_parent)

    answers = [zone_soa_record]
    answers_formatted = [f"RESOLVER: {answer.nameserver}\n{answer.response}" for answer in answers]

    return [(set(), "\n\n".join(answers_formatted))]


def get_parent_zone_soa(name: Name) -> Answer:
    while True:
        try:
            return dns.resolver.resolve(name, dns.rdatatype.SOA)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            pass

        try:
            name = name.parent()
        except dns.name.NoParent:
            raise ZoneNotFoundException
