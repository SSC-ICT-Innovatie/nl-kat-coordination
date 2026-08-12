#!/usr/bin/env python3

"""
This is fierce version 1.4.0, with some small changes.
https://github.com/mschwager/fierce
"""

import argparse
import concurrent.futures
import contextlib
import functools
import http.client
import ipaddress
import itertools
import multiprocessing
import os
import random
import socket
import sys
import time
from typing import Any

import dns.exception
import dns.name
import dns.query
import dns.resolver
import dns.reversename
import dns.zone


def fatal(msg, _return_code=-1):
    raise Exception(msg)


def print_subdomain_result(url, ip, nearby=None):
    output = {"url": str(url), "ip": str(ip)}

    if nearby:
        output["nearby"] = nearby

    return output


def unvisited_closure():
    visited: set = set()

    def inner(l):  # noqa: E741
        nonlocal visited
        result = set(l).difference(visited)
        visited.update(l)
        return result

    return inner


def find_subdomain_list_file(filename):
    # First check the list directory relative to where we are. This
    # will typically happen if they simply cloned the Github repository
    filename_path = os.path.join(os.path.dirname(__file__), "lists", filename)
    if os.path.exists(filename_path):
        return os.path.abspath(filename_path)
    else:
        return filename


def head_request(url, timeout=2):
    conn = http.client.HTTPConnection(url, timeout=timeout)

    try:
        conn.request("HEAD", "/")
        resp = conn.getresponse()
        return resp.getheaders()
    except (ConnectionError, socket.gaierror, TimeoutError, OSError):
        return []
    finally:
        conn.close()


def concatenate_subdomains(domain, subdomains):
    subdomains = [nested_subdomain for subdomain in subdomains for nested_subdomain in subdomain.strip(".").split(".")]

    result = dns.name.Name(tuple(subdomains) + domain.labels)

    if not result.is_absolute():
        result = result.concatenate(dns.name.root)

    return result


def query(resolver, domain, record_type="A", tcp=False):
    try:
        resp = resolver.query(domain, record_type, raise_on_no_answer=False, tcp=tcp)
        if resp.response.answer:
            return resp

        # If we don't receive an answer from our current resolver let's
        # assume we received information on nameservers we can use and
        # perform the same query with those nameservers
        if resp.response.additional and resp.response.authority:
            ns = [rdata.address for additional in resp.response.additional for rdata in additional.items]
            resolver.nameservers = ns
            return query(resolver, domain, record_type, tcp=tcp)

        return None
    except (dns.resolver.NXDOMAIN, dns.resolver.NoNameservers, dns.exception.Timeout, ValueError):
        return None


def reverse_query(resolver, ip, tcp=False):
    return query(resolver, dns.reversename.from_address(ip), record_type="PTR", tcp=tcp)


def recursive_query(resolver, domain, record_type="NS", tcp=False):
    query_domain = str(domain)
    query_response = None
    try:
        while query_response is None:
            query_response = query(resolver, query_domain, record_type, tcp=tcp)
            query_domain = query_domain.split(".", 1)[1]
    except IndexError:
        return None

    return query_response


def zone_transfer(address, domain):
    try:
        return dns.zone.from_xfr(dns.query.xfr(address, domain))
    except (ConnectionError, EOFError, TimeoutError, dns.exception.DNSException):
        return None


def get_class_c_network(ip):
    ip = int(ip)
    floored = ipaddress.ip_address(ip - (ip % (2**8)))
    class_c = ipaddress.IPv4Network(f"{floored}/24")

    return class_c


def default_expander(ip):
    return [ip]


def traverse_expander(ip, n=5):
    ip = int(ip)
    class_c_floor = ip - (ip % 256)
    class_c_ceiling = class_c_floor + 255

    ip_min = max(ip - n, class_c_floor)
    ip_max = min(ip + n, class_c_ceiling)
    return [ipaddress.IPv4Address(i) for i in range(ip_min, ip_max + 1)]


def wide_expander(ip):
    class_c = get_class_c_network(ip)

    result = list(class_c)

    return result


def range_expander(ip):
    try:
        network = ipaddress.IPv4Network(ip)
    except ipaddress.AddressValueError:
        fatal(f"Invalid IPv4 CIDR: {ip!r}")

    result = list(network)

    return result


def default_filter(address):
    return True


def search_filter(domains, address):
    return any(domain in address for domain in domains)


def find_nearby(resolver, ips, filter_func=None):
    if filter_func is None:
        filter_func = default_filter

    str_ips = [str(ip) for ip in ips]

    # https://docs.python.org/3.5/library/concurrent.futures.html#concurrent.futures.ThreadPoolExecutor
    max_workers = multiprocessing.cpu_count() * 5

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        reversed_ips = {
            ip: query_result
            for ip, query_result in zip(
                str_ips, executor.map(reverse_query, itertools.repeat(resolver, len(str_ips)), str_ips)
            )
        }

    reversed_ips = {k: v[0].to_text() for k, v in reversed_ips.items() if v is not None and filter_func(v[0].to_text())}

    return reversed_ips


def get_stripped_file_lines(filename):
    """
    Return lines of a file with whitespace removed
    """
    try:
        with open(filename) as f:
            lines = f.readlines()
    except FileNotFoundError:
        fatal(f"Could not open file: {filename!r}")

    return [line.strip() for line in lines]


def get_subdomains(subdomains, subdomain_filename):
    """
    Return subdomains with the following priority:
        1. Subdomains list provided as an argument
        2. A filename containing a list of subdomains
    """
    if subdomains:
        return subdomains
    elif subdomain_filename:
        return get_stripped_file_lines(subdomain_filename)

    return []


def update_resolver_nameservers(resolver, nameservers, nameserver_filename):
    """
    Update a resolver's nameservers. The following priority is taken:
        1. Nameservers list provided as an argument
        2. A filename containing a list of nameservers
        3. The original nameservers associated with the resolver
    """
    if nameservers:
        resolver.nameservers = nameservers
    elif nameserver_filename:
        nameservers = get_stripped_file_lines(nameserver_filename)
        resolver.nameservers = nameservers
    else:
        # Use original nameservers
        pass

    return resolver


def fierce(**kwargs):
    output: dict[str, Any] = {}
    resolver = dns.resolver.Resolver()

    resolver = update_resolver_nameservers(resolver, kwargs["dns_servers"], kwargs["dns_file"])

    if kwargs.get("range"):
        range_ips = range_expander(kwargs.get("range"))
        nearby = find_nearby(resolver, range_ips)
        if nearby:
            pass

    if not kwargs.get("domain"):
        return

    domain = dns.name.from_text(kwargs["domain"])
    if not domain.is_absolute():
        domain = domain.concatenate(dns.name.root)

    ns = recursive_query(resolver, domain, "NS", tcp=kwargs["tcp"])

    domain_name_servers = [n.to_text() for n in ns] if ns else []

    output["NS"] = domain_name_servers if ns else "failure"

    soa = recursive_query(resolver, domain, record_type="SOA", tcp=kwargs["tcp"])
    if soa:
        soa_mname = soa[0].mname
        master = query(resolver, soa_mname, record_type="A", tcp=kwargs["tcp"])
        master_address = master[0].address
        output["SOA"] = f"{soa_mname} ({master_address})"
    else:
        fatal("Failed to lookup NS/SOA, Domain does not exist")

    zone = zone_transfer(master_address, domain)
    if zone:
        return

    random_subdomain = str(random.randint(10_000_000_000, 100_000_000_000))  # noqa DUO102, non-cryptographic random use
    random_domain = concatenate_subdomains(domain, [random_subdomain])
    wildcard = query(resolver, random_domain, record_type="A", tcp=kwargs["tcp"])
    wildcard_ips = {rr.address for rr in wildcard.rrset} if wildcard else set()

    subdomains = get_subdomains(kwargs["subdomains"], kwargs["subdomain_file"])

    filter_func = None
    if kwargs.get("search"):
        filter_func = functools.partial(search_filter, kwargs["search"])

    expander_func = default_expander
    if kwargs.get("wide"):
        expander_func = wide_expander
    elif kwargs.get("traverse"):
        expander_func = functools.partial(traverse_expander, n=kwargs["traverse"])

    unvisited = unvisited_closure()

    output["subdomains"] = {}
    for subdomain in subdomains:
        url = concatenate_subdomains(domain, [subdomain])
        record = query(resolver, url, record_type="A", tcp=kwargs["tcp"])

        if record is None or record.rrset is None:
            continue

        ips = [rr.address for rr in record.rrset]
        if wildcard_ips == set(ips):
            continue

        ip = ipaddress.IPv4Address(ips[0])

        if "connect" in kwargs and not ip.is_private:
            head_request(str(ip))

        ips = expander_func(ip)
        unvisited_ips = unvisited(ips)

        nearby = find_nearby(resolver, unvisited_ips, filter_func=filter_func)

        output["subdomains"][subdomain] = print_subdomain_result(url, ip, nearby=nearby)

        if kwargs.get("delay"):
            time.sleep(kwargs["delay"])

    return output


def parse_args(args):
    p = argparse.ArgumentParser(
        description="""
        A DNS reconnaissance tool for locating non-contiguous IP space.
        """,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    p.add_argument("--domain", action="store", help="domain name to test")
    p.add_argument("--connect", action="store_true", help="attempt HTTP connection to non-RFC 1918 hosts")
    p.add_argument("--wide", action="store_true", help="scan entire class c of discovered records")
    p.add_argument(
        "--traverse",
        action="store",
        type=int,
        default=5,
        help="scan IPs near discovered records, this won't enter adjacent class c's",
    )
    p.add_argument("--search", action="store", nargs="+", help="filter on these domains when expanding lookup")
    p.add_argument("--range", action="store", help="scan an internal IP range, use cidr notation")
    p.add_argument("--delay", action="store", type=float, default=None, help="time to wait between lookups")

    subdomain_group = p.add_mutually_exclusive_group()
    subdomain_group.add_argument("--subdomains", action="store", nargs="+", help="use these subdomains")
    subdomain_group.add_argument(
        "--subdomain-file",
        action="store",
        default="5000.txt",
        help="use subdomains specified in this file (one per line)",
    )

    dns_group = p.add_mutually_exclusive_group()
    dns_group.add_argument("--dns-servers", action="store", nargs="+", help="use these dns servers for reverse lookups")
    dns_group.add_argument(
        "--dns-file", action="store", help="use dns servers specified in this file for reverse lookups (one per line)"
    )
    p.add_argument("--tcp", action="store_true", help="use TCP instead of UDP")

    args = p.parse_args(args)

    # Attempt to intelligently find the subdomain list depending on
    # how this library was installed.
    if args.subdomain_file and not os.path.exists(args.subdomain_file):
        args.subdomain_file = find_subdomain_list_file(args.subdomain_file)

    return args


def main():
    args = parse_args(sys.argv[1:])

    with contextlib.suppress(KeyboardInterrupt):
        fierce(**vars(args))


if __name__ == "__main__":
    main()
