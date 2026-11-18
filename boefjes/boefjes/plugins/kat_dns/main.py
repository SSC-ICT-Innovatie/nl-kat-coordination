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


class TimeoutException(Exception):
    pass


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

    # Two separate ledgers:
    # - `answers` holds records that belong in the raw output (metadata and
    #   directly-owned records); a foreign-owner SOA is resolved but excluded.
    # - `outcomes` tracks the per-type result of every scan-subject query; the
    #   parent-zone SOA metadata walk is *not* scan-subject and never counts,
    #   even when it succeeds.
    answers: list[Answer] = []
    if "SOA" in record_types:
        # The parent-zone SOA is metadata the normalizer uses for zone
        # attribution, not part of the scan result: a timeout here weakens
        # attribution but must not gate (or discard) the record lookups below,
        # which may well succeed.
        try:  # noqa: SIM105 (deliberate swallow, see comment above)
            answers.append(get_parent_zone_soa(resolver, requested_dns_name))
        except dns.resolver.Timeout:
            pass

    # outcome per scan-subject record type: "answer", "noanswer", "nxdomain"
    # or "timeout". A foreign-owner SOA (CNAME follow) belongs to another zone
    # and is not conclusive evidence for this hostname.
    outcomes: dict[str, str] = {}
    for type_ in record_types:
        try:
            answer: Answer = resolver.resolve(hostname, type_)
            if type_ == "SOA" and (answer.rrset is None or answer.rrset.name != requested_dns_name):
                outcomes[type_] = "timeout"  # inconclusive for this hostname
                continue
            outcomes[type_] = "answer"
            answers.append(answer)
        except dns.resolver.Timeout:
            # Inconclusive: does not count as either answer or negative.
            outcomes[type_] = "timeout"
        except dns.resolver.NoAnswer:
            # Definitive negative from the nameserver: not inconclusive.
            outcomes[type_] = "noanswer"
        except dns.resolver.NXDOMAIN:
            return [(set(), "NXDOMAIN")]

    # Vacuously true when record_types is empty, so an all-timeout of the
    # email-security lookups below can still produce error/timeout.
    all_record_queries_inconclusive = all(outcome == "timeout" for outcome in outcomes.values())

    answers_formatted = [f"RESOLVER: {answer.nameserver}\n{answer.response}" for answer in answers]

    results = {
        "dns_records": "\n\n".join(answers_formatted),
        "dmarc_response": get_email_security_records(resolver, hostname, "_dmarc"),
        "dkim_response": get_email_security_records(resolver, hostname, "_domainkey"),
        # Per-type outcome of every scan-subject query: "answer", "noanswer",
        # "nxdomain" or "timeout". A missing record is only meaningful when
        # its query actually got an answer: downstream absence checks (SPF,
        # DMARC, CAA) must not fire off a timeout. The normalizer currently
        # ignores this key; it is carried in the raw so they can start
        # consulting it without another raw-format change.
        "record_outcomes": outcomes,
    }
    # All-or-nothing: only report a scan-wide timeout when nothing at all was
    # resolved definitively (no answer, no NoAnswer, no NXDOMAIN) and every
    # scan-subject record query was inconclusive. The parent-zone SOA is
    # metadata and does not count in either direction. Partial timeouts still
    # produce a result; the individual timeouts of the record queries are
    # visible in it through the missing answers.
    everything_timed_out = (
        not any(o in ("answer", "noanswer") for o in outcomes.values())
        and all_record_queries_inconclusive
        and results["dmarc_response"] == "Timeout"
        and results["dkim_response"] == "Timeout"
    )
    if everything_timed_out:
        # Not a hard failure: the nameserver simply did not answer in time, so
        # report the timeout mime-type (task ends in the TIMEOUT state).
        return [({"error/timeout"}, "No answers from DNS-Server due to timeouts.")]
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
