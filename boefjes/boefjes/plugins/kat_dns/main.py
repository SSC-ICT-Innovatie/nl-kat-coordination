"""Boefje script for getting dns records"""

import json
import logging
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
    selected = {record.strip().upper() for record in requested_record_types.split(",")}
    unsupported = selected - DEFAULT_RECORD_TYPES
    if unsupported:
        raise ValueError(f"Unsupported DNS record types: {', '.join(sorted(unsupported))}")
    return selected


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    hostname = boefje_meta["arguments"]["input"]["name"]

    requested_dns_name = dns.name.from_text(hostname)
    resolver = dns.resolver.Resolver()
    # https://dnspython.readthedocs.io/en/stable/_modules/dns/edns.html
    # enable EDE to get the DNSSEC Bogus return values if the server supports it # codespell-ignore
    resolver.use_edns(options=[EDEOption(15)])
    nameserver = getenv("REMOTE_NS", "1.1.1.1")
    resolver.nameservers = [nameserver]

    record_types = get_record_types()
    answers = []
    timed_out = False
    query_errors: dict[str, str] = {}
    if "SOA" in record_types:
        try:
            answers.append(get_parent_zone_soa(resolver, requested_dns_name))
        except (dns.resolver.Timeout, dns.resolver.NoNameservers, ZoneNotFoundException) as error:
            logger.warning("Could not discover SOA for %s: %s", hostname, error)
            timed_out = isinstance(error, dns.resolver.Timeout)

    for type_ in sorted(record_types):
        try:
            answer: Answer = resolver.resolve(hostname, type_)
            answers.append(answer)
        except dns.resolver.NoAnswer:
            query_errors[type_] = "NOANSWER"
        except dns.resolver.Timeout:
            timed_out = True
            query_errors[type_] = "TIMEOUT"
        except dns.resolver.NoNameservers as error:
            query_errors[type_] = "NO_NAMESERVERS"
            logger.warning("DNS query for %s (%s) failed: %s", hostname, type_, error)
        except dns.resolver.NXDOMAIN:
            query_errors[type_] = "NXDOMAIN"
            # Only emit the legacy NXDOMAIN marker when there are no successful
            # answers or transient errors to preserve. An isolated negative
            # response must not discard records already collected.
            if not answers and all(status == "NXDOMAIN" for status in query_errors.values()):
                return [(set(), "NXDOMAIN")]

    answers_formatted = [f"RESOLVER: {answer.nameserver}\n{answer.response}" for answer in answers]

    results = {
        "dns_records": "\n\n".join(answers_formatted),
        "query_errors": query_errors,
        "dmarc_response": get_email_security_records(resolver, hostname, "_dmarc"),
        "dkim_response": get_email_security_records(resolver, hostname, "_domainkey"),
    }
    if (
        not answers_formatted
        and timed_out
        and results["dmarc_response"] == "Timeout"
        and results["dkim_response"] == "Timeout"
    ):
        raise TimeoutException("No answers from DNS-Server due to timeouts.")
    return [(set(), json.dumps(results))]


def get_parent_zone_soa(resolver: dns.resolver.Resolver, name: Name) -> Answer:
    while True:
        try:
            return resolver.resolve(name, dns.rdatatype.SOA)
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
        for server_error in error.kwargs.get("errors", []):
            if len(server_error) < 5 or server_error[3] != "SERVFAIL":
                continue
            response = server_error[4]
            for option in getattr(response, "options", ()):
                if isinstance(option, EDEOption) and option.code in (1, 2, 5, 6, 7, 8, 9, 10, 11, 12):
                    return "DNSSECFAIL"
        raise  # Not dnssec related, unhandled, raise.
    except dns.resolver.NXDOMAIN:
        return "NXDOMAIN"
    except dns.resolver.Timeout:
        return "Timeout"
