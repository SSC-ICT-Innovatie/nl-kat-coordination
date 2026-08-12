from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.web import HostnameHTTPURL, HTTPResource, Website


def run(hostname: Hostname, additional_oois: list[HostnameHTTPURL | Website], config: dict[str, Any]) -> Iterator[OOI]:
    hostname_http_urls = [
        hostname_http_url for hostname_http_url in additional_oois if isinstance(hostname_http_url, HostnameHTTPURL)
    ]
    websites = [website for website in additional_oois if isinstance(website, Website)]

    # HTTPResource is cartesian product of HostnameHTTPURL and Websites
    for hostname_http_url in hostname_http_urls:
        for website in websites:
            # only create resource if ports are the same and schemes are the same
            if (
                int(website.ip_service.tokenized.ip_port.port) == hostname_http_url.port
                and website.ip_service.tokenized.service.name == hostname_http_url.scheme.value
            ):
                yield HTTPResource(website=website.reference, web_url=hostname_http_url.reference)
