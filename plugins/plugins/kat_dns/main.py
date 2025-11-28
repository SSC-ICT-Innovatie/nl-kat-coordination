import argparse
import json
import os
import re
from collections import defaultdict
from os import getenv

import dns
import httpx
from dns.edns import EDECode, EDEOption
from dns.message import from_text
from dns.rdtypes.ANY.CAA import CAA
from dns.rdtypes.ANY.CNAME import CNAME
from dns.rdtypes.ANY.MX import MX
from dns.rdtypes.ANY.NS import NS
from dns.rdtypes.ANY.TXT import TXT
from dns.rdtypes.IN.A import A
from dns.rdtypes.IN.AAAA import AAAA
from dns.resolver import Answer
from tldextract import tldextract

DEFAULT_RECORD_TYPES = {"A", "AAAA", "CAA", "CERT", "RP", "SRV", "TXT", "MX", "NS", "CNAME", "DNAME"}


def get_record_types(records: list[str]) -> set[str]:
    parsed_requested_record_types = map(lambda x: re.sub(r"[^A-Za-z]", "", x.upper()), records)
    return set(parsed_requested_record_types).intersection(DEFAULT_RECORD_TYPES)


def mail_records(hostname: str) -> list:
    resolver = dns.resolver.Resolver()
    root_domain = tldextract.extract(hostname).registered_domain.rstrip(".")
    results: list[dict[str, str | int]] = [
        {"object_type": "Hostname", "network": "internet", "name": hostname},
        {"object_type": "Hostname", "network": "internet", "name": root_domain, "root": True},
    ]

    for domain in {root_domain, hostname}:
        dmarc_results = get_email_security_records(resolver, domain, "_dmarc")

        # dkim_res = get_email_security_records(resolver, hostname, "_domainkey")
        # TODO: DKIM
        # if dkim_res not in ["NXDOMAIN", "Timeout", "DNSSECFAIL"] and dkim_res.split("\n")[2] == "rcode NOERROR":
        #     results.append({"object_type": "DKIMExists", "hostname": hostname})

        if dmarc_results in ["NXDOMAIN", "Timeout"]:
            continue

        for rrset in from_text(dmarc_results).answer:
            for rr in rrset:
                if isinstance(rr, TXT):
                    results.append(
                        {
                            "object_type": "DNSTXTRecord",
                            "hostname": f"internet|{domain}".lower(),
                            "value": str(rr).strip('"'),
                            "prefix": "_dmarc",
                            "ttl": rrset.ttl,
                        }
                    )

    return results


def generic_records(hostname: str, record_types: set[str]) -> list[dict[str, str | int]]:
    resolver = dns.resolver.Resolver()

    # https://dnspython.readthedocs.io/en/stable/_modules/dns/edns.html
    # enable EDE to get the DNSSEC Bogus return values if the server supports it # codespell-ignore
    resolver.use_edns(options=[EDEOption(EDECode.BLOCKED)])
    nameserver = getenv("REMOTE_NS", "1.1.1.1")
    resolver.nameservers = [nameserver]

    answers = []
    for type_ in record_types:
        try:
            answer: Answer = resolver.resolve(hostname, type_)
            answers.append(answer)
        except (dns.resolver.NoAnswer, dns.resolver.Timeout, NotImplementedError):
            pass
        except dns.resolver.NXDOMAIN:
            return []

    if not answers:
        return []

    hostname_store = {}
    record_store = []

    def register_hostname(name: str) -> dict:
        hostname: dict[str, str | int] = {"object_type": "Hostname", "network": "internet", "name": name.rstrip(".")}
        hostname_store[hostname["name"]] = hostname
        return hostname

    def register_record(record: dict) -> dict:
        record_store.append(record)
        return record

    register_hostname(hostname)

    results: list[dict[str, str | int]] = []

    for answer in answers:
        for rrset in answer.response.answer:
            for rr in rrset:
                record_hostname = register_hostname(str(rrset.name))
                default_args = {
                    "hostname": f"internet|{record_hostname['name']}".lower(),
                    "value": str(rr),
                    "ttl": rrset.ttl,
                }

                if isinstance(rr, A):
                    ipv4: dict[str, str | int] = {"object_type": "IPAddress", "network": "internet", "address": str(rr)}
                    results.append(ipv4)
                    register_record(
                        {"object_type": "DNSARecord", "ip_address": f"internet|{ipv4['address']}", **default_args}
                    )

                if isinstance(rr, AAAA):
                    ipv6: dict[str, str | int] = {"object_type": "IPAddress", "network": "internet", "address": str(rr)}
                    results.append(ipv6)
                    register_record(
                        {"object_type": "DNSAAAARecord", "ip_address": f"internet|{ipv6['address']}", **default_args}
                    )

                if isinstance(rr, TXT):
                    # TODO: concatenated txt records should be handled better
                    # see https://www.rfc-editor.org/rfc/rfc1035 3.3.14
                    default_args["value"] = str(rr).strip('"').replace('" "', "")
                    register_record({"object_type": "DNSTXTRecord", **default_args})

                if isinstance(rr, MX):
                    if str(rr.exchange) != ".":
                        mail_fqdn = register_hostname(str(rr.exchange))
                        mail_hostname_reference = mail_fqdn["name"]
                    else:
                        continue
                    register_record(
                        {
                            "object_type": "DNSMXRecord",
                            "mail_server": f"internet|{mail_hostname_reference}",
                            "preference": rr.preference,
                            **default_args,
                        }
                    )

                if isinstance(rr, NS):
                    ns_fqdn = register_hostname(str(rr.target))
                    register_record(
                        {
                            "object_type": "DNSNSRecord",
                            "name_server": f"internet|{ns_fqdn['name']}".lower(),
                            **default_args,
                        }
                    )

                if isinstance(rr, CNAME):
                    target_fqdn = register_hostname(str(rr.target))
                    register_record(
                        {
                            "object_type": "DNSCNAMERecord",
                            "target": f"internet|{target_fqdn['name']}".lower(),
                            **default_args,
                        }
                    )

                if isinstance(rr, CAA):
                    record_value = str(rr).split(" ", 2)
                    default_args["flags"] = min(max(0, int(record_value[0])), 255)
                    default_args["tag"] = re.sub("[^\\w]", "", record_value[1].lower())
                    default_args["value"] = record_value[2]
                    register_record({"object_type": "DNSCAARecord", **default_args})

    results.extend(hostname_store.values())
    results.extend(record_store)

    return results


def get_email_security_records(resolver: dns.resolver.Resolver, hostname: str, record_subdomain: str) -> str:
    try:
        answer = resolver.resolve(f"{record_subdomain}.{hostname}", "TXT", raise_on_no_answer=False)
        if answer.rrset is None:
            return "NXDOMAIN"
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


def main():
    token = os.getenv("OPENKAT_TOKEN")
    base_url = os.getenv("OPENKAT_API")

    if not token:
        raise Exception("No OPENKAT_TOKEN env variable")
    if not base_url:
        raise Exception("No OPENKAT_API env variable")

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("hostname")
    parser.add_argument("record_types", nargs="*")
    parser.add_argument("-m", action="store_true", dest="mail_server")
    args = parser.parse_args()

    record_types = DEFAULT_RECORD_TYPES if not args.record_types else get_record_types(args.record_types)
    hostname = args.hostname.rstrip(".")
    results = generic_records(hostname, record_types)
    results.extend(mail_records(hostname))

    client = httpx.Client(base_url=base_url, headers={"Authorization": "Token " + token})

    if not results:
        response = client.get(f"/objects/hostname/?name={hostname}").raise_for_status().json()
        if response["results"]:
            client.delete(
                f"/objects/hostname/internet|{hostname}/dnsrecord/",
                params={"record_id": [rec["id"] for rec in response["results"][0]["dns_records"]]},
            ).raise_for_status()
        return

    grouped = defaultdict(list)
    for result in results:
        object_type = result.pop("object_type")
        if not isinstance(object_type, str):
            continue

        grouped[object_type.lower()].append(result)

    hostnames_and_ips = {"hostname": grouped.pop("hostname", []), "ipaddress": grouped.pop("ipaddress", [])}
    response = client.post("/objects/", json=hostnames_and_ips).raise_for_status()  # make sure these exist
    dns_response = client.post("/objects/", json=grouped).raise_for_status().json()

    records = []
    for host in response.json().get("hostname", []):
        if host["name"] == hostname:
            records = host["dns_records"]
            break

    to_be_deleted: dict[str, dict] = {dns.pop("id"): dns for dns in records}

    for obj_type, recs in dns_response.items():
        for rec in recs:
            if rec["id"] in to_be_deleted:
                del to_be_deleted[rec["id"]]

    if to_be_deleted:
        params = {"record_id": list(to_be_deleted.keys())}
        client.delete(f"/objects/hostname/internet|{hostname}/dnsrecord/", params=params).raise_for_status()

    print(json.dumps(results))  # noqa: T201


if __name__ == "__main__":
    main()
