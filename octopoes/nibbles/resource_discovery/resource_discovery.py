from collections.abc import Iterator

from octopoes.models import OOI
from octopoes.models.ooi.web import HostnameHTTPURL, HTTPResource, Website


def nibble(hostname_http_url: HostnameHTTPURL, website: Website) -> Iterator[OOI]:
    yield HTTPResource(website=website.reference, web_url=hostname_http_url.reference)
