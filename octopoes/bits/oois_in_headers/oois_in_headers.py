import re
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from pydantic import ValidationError

from octopoes.models import OOI
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network
from octopoes.models.ooi.web import URL, HTTPHeader, HTTPHeaderHostname, HTTPHeaderURL


def is_url(input_str):
    result = urlparse(input_str)
    return bool(result.scheme)


def get_ignored_url_params(config: dict, config_key: str, default: list) -> list[str]:
    ignored_url_params = config.get(config_key)
    if ignored_url_params is None:
        return default
    return [param.strip() for param in ignored_url_params.split(",")] if ignored_url_params else []


def remove_ignored_params(url: str, ignored_params: list[str]) -> str:
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    if not query_params:
        return url
    filtered_params = {k: v for k, v in query_params.items() if k.lower() not in ignored_params}
    new_query = urlencode(filtered_params, doseq=True)
    new_url = urlunparse(
        (parsed_url.scheme, parsed_url.netloc, parsed_url.path, parsed_url.params, new_query, parsed_url.fragment)
    )
    return new_url


def run(input_ooi: HTTPHeader, additional_oois: list, config: dict[str, Any]) -> Iterator[OOI]:
    network = Network(name=input_ooi.reference.tokenized.resource.web_url.netloc.network.name)

    if input_ooi.key.lower() == "location":
        ignored_url_params = get_ignored_url_params(config, "ignored_url_parameters", [])
        if is_url(input_ooi.value):
            u = URL(raw=remove_ignored_params(input_ooi.value, ignored_url_params), network=network.reference)
        else:
            # url is not a url but a relative path
            http_url = input_ooi.reference.tokenized.resource.web_url
            # allow for ipaddress http urls
            netloc = http_url.netloc.name if "name" in http_url.netloc.root else http_url.netloc.address
            original_url = f"{http_url.scheme}://{netloc}{http_url.path}"
            u = URL(raw=urljoin(original_url, input_ooi.value), network=network.reference)
        yield u
        http_header_url = HTTPHeaderURL(header=input_ooi.reference, url=u.reference)
        yield http_header_url

    if input_ooi.key.lower() == "content-security-policy":
        urls_and_hostname = re.findall(r"(?:(?:https?|ftp):\/\/)?[\w/\-?=%.]+\.[\w/\-&?=%.]+", input_ooi.value)

        for url_or_hostname in urls_and_hostname:
            try:
                u = URL(raw=url_or_hostname, network=network.reference)
                yield u
                http_header_url = HTTPHeaderURL(header=input_ooi.reference, url=u.reference)
                yield http_header_url
            # some hostnames get classified as urls by the regex here, they need to be parsed by another bit
            except ValidationError:
                name = url_or_hostname if url_or_hostname[0] != "." else url_or_hostname[1:]
                h = Hostname(name=name, network=network.reference)
                yield h
                http_header_hostname = HTTPHeaderHostname(header=input_ooi.reference, hostname=h.reference)
                yield http_header_hostname
