"""Boefje script for getting dns records"""

import json
import logging
import re
from os import getenv

import dns.resolver
from dns.edns import EDEOption
from dns.name import Name
from dns.resolver import Answer

logger = logging.getLogger(__name__)
DEFAULT_RECORD_TYPES = {
    "A",
    "AAAA",
    "CAA",
    "CERT",
    "RP",
    "SRV",
    "TXT",
    "MX",
    "NS",
    "CNAME",
    "DNAME",
    "SOA",
    "LOC",
    "GPOS",
}


class ZoneNotFoundException(Exception):
    pass


def get_record_types() -> set[str]:
    requested_record_types = getenv("RECORD_TYPES", "")
    if not requested_record_types:
        return DEFAULT_RECORD_TYPES
    parsed_requested_record_types = map(
        lambda x: re.sub(r"[^A-Za-z]", "", x), requested_record_types.upper().split(",")
    )
    return set(parsed_requested_record_types).intersection(DEFAULT_RECORD_TYPES)


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    hostname = boefje_meta["arguments"]["input"]["name"]

    requested_dns_name = dns.name.from_text(hostname)
    resolver = dns.resolver.Resolver()
    # https://dnspython.readthedocs.io/en/stable/_modules/dns/edns.html
    # enable EDE to get the DNSSEC Bogus return values if the server supports it # codespell-ignore
    resolver.use_edns(options=[EDEOption(15)])
    nameserver = getenv("REMOTE_NS", "1.1.1.1")
    resolver.nameservers = [nameserver]
    # Can be overridden through the plugin settings, see schema.json.
    resolver.timeout = float(getenv("DNS_TIMEOUT", "5"))
    resolver.lifetime = float(getenv("DNS_LIFETIME", "30"))

    record_types = get_record_types()

    # Any timeout discards the whole scan: forwarding a partial result would
    # garbage-collect records that merely timed out, because the normalizer
    # treats records missing from the output as gone. A timeout therefore
    # yields no output at all and the task ends in the rerunnable TIMEOUT
    # state, so the data from the previous scan stays intact until the retry.
    def timed_out() -> list[tuple[set[str], bytes | str]]:
        return [
            ({"error/timeout"}, f"DNS queries for {hostname} timed out; nothing reported, the scan will be retried.")
        ]

    answers: list[Answer] = []
    if "SOA" in record_types:
        try:
            answers.append(get_parent_zone_soa(resolver, requested_dns_name))
        except dns.resolver.Timeout:
            return timed_out()

    for type_ in record_types:
        try:
            answer: Answer = resolver.resolve(hostname, type_)
            # An SOA lookup can follow a CNAME into a different DNS zone.
            # Only treat a directly-owned SOA as a record for this hostname.
            if type_ == "SOA" and (answer.rrset is None or answer.rrset.name != requested_dns_name):
                continue
            answers.append(answer)
        except dns.resolver.Timeout:
            return timed_out()
        except dns.resolver.NoAnswer:
            pass
        except dns.resolver.NXDOMAIN:
            return [(set(), "NXDOMAIN")]

    dmarc_response = get_email_security_records(resolver, hostname, "_dmarc")
    dkim_response = get_email_security_records(resolver, hostname, "_domainkey")
    if dmarc_response == "Timeout" or dkim_response == "Timeout":
        return timed_out()

    answers_formatted = [f"RESOLVER: {answer.nameserver}\n{answer.response}" for answer in answers]
    results = {
        "dns_records": "\n\n".join(answers_formatted),
        "dmarc_response": dmarc_response,
        "dkim_response": dkim_response,
    }
    return [(set(), json.dumps(results))]


def get_parent_zone_soa(resolver: dns.resolver.Resolver, name: Name) -> Answer:
    while True:
        try:
            answer = resolver.resolve(name, dns.rdatatype.SOA)
            # A CNAME at `name` can cause resolve() to return the target's
            # SOA. Keep walking the original hostname's parents instead.
            if answer.rrset is not None and answer.rrset.name == name:
                return answer
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            pass

        try:
            name = name.parent()
        except dns.name.NoParent:
            raise ZoneNotFoundException


def get_email_security_records(resolver: dns.resolver.Resolver, hostname: str, record_subdomain: str) -> str:
    try:
        answer = resolver.resolve(f"{record_subdomain}.{hostname}", "TXT", raise_on_no_answer=False)
        return answer.response.to_text()
    except dns.resolver.NoNameservers as error:
        # no servers responded happily, we'll check the response from the first
        # https://dnspython.readthedocs.io/en/latest/_modules/dns/rcode.html
        # https://www.rfc-editor.org/rfc/rfc8914#name-extended-dns-error-code-6-d
        firsterror = error.kwargs["errors"][0]
        if firsterror[3] == "SERVFAIL":
            edeerror = int(firsterror[4].options[0].code)
            if edeerror in (1, 2, 5, 6, 7, 8, 9, 10, 11, 12):  # DNSSEC error codes defined in RFC 8914
                return "DNSSECFAIL"  # returned when the resolver indicates a DNSSEC failure.
        raise  # Not dnssec related, unhandled, raise.
    except dns.resolver.NXDOMAIN:
        return "NXDOMAIN"
    except dns.resolver.Timeout:
        return "Timeout"
