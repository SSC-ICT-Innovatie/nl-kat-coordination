"""Boefje script for getting namserver version"""

import json
from os import getenv

import dns
import dns.message
import dns.query


def run(boefje_meta: dict) -> list[tuple[set, str | bytes]]:
    input_ = boefje_meta["arguments"]["input"]  # input is IPService
    ip_port = input_["ip_port"]
    if input_["service"]["name"] != "domain":
        return [({"error/boefje"}, "Not a DNS service")]

    ip = ip_port["address"]["address"]
    port = int(ip_port["port"])
    protocol = ip_port["protocol"]

    timeout = float(getenv("TIMEOUT", 30))

    method = dns.query.udp if protocol == "udp" else dns.query.tcp

    queries = [
        dns.message.make_query("VERSION.BIND", dns.rdatatype.TXT, dns.rdataclass.CHAOS),
        dns.message.make_query("VERSION.SERVER", dns.rdatatype.TXT, dns.rdataclass.CHAOS),
    ]

    results = []
    for query in queries:
        response = method(query, where=ip, timeout=timeout, port=port)

        try:
            answer = response.answer[0]
            results.append(answer.to_rdataset().pop().strings[0].decode())
        except IndexError:
            pass

    return [(set(), json.dumps(results))]
