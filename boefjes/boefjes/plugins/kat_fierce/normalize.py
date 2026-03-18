import json
from collections.abc import Iterable
from ipaddress import IPv4Address, ip_address

from tldextract import tldextract

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models.ooi.dns.zone import Hostname, ResolvedHostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, Network


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    results = json.loads(raw)

    internet = Network(name="internet")
    yield internet

    for _, subdomain in results["subdomains"].items():
        hostname = subdomain["url"].rstrip(".")
        registered_domain = tldextract.extract(hostname).registered_domain

        registered_domain_ooi = Hostname(name=registered_domain, network=internet.reference)
        yield registered_domain_ooi
        hostname_ooi = Hostname(
            name=hostname, network=internet.reference, registered_domain=registered_domain_ooi.reference
        )
        yield hostname_ooi

        resolved_ip = subdomain["ip"]
        if isinstance(ip_address(resolved_ip), IPv4Address):
            resolved_ip_ooi = IPAddressV4(network=internet.reference, address=resolved_ip)
        else:
            resolved_ip_ooi = IPAddressV6(network=internet.reference, address=resolved_ip)
        yield resolved_ip_ooi

        resolved_hostname_ooi = ResolvedHostname(hostname=hostname_ooi.reference, address=resolved_ip_ooi.reference)
        yield resolved_hostname_ooi
