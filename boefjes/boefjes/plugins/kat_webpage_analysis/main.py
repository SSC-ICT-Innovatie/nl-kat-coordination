import ipaddress
import json
import mimetypes
from os import getenv
from urllib.parse import urljoin, urlparse, urlunsplit

import requests
from forcediphttpsadapter.adapters import ForcedIPHTTPSAdapter
from requests import Session

# TODO: refactor
from boefjes.plugins.kat_webpage_analysis.har.requests import create_har_object

ALLOWED_CONTENT_TYPES = mimetypes.types_map.values()

DEFAULT_PORTS = {"http": 80, "https": 443}
# Cap on same-resource redirect hops (see do_request).
MAX_SAME_RESOURCE_REDIRECTS = 5


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]
    useragent = getenv("USERAGENT", default="OpenKAT")

    uri = get_uri(input_)
    ip = input_["website"]["ip_service"]["ip_port"]["address"]["address"]
    # Code from https://github.com/Roadmaster/forcediphttpsadapter/blob/master/example.py
    url_parts = urlparse(uri)
    hostname = url_parts.netloc
    session = requests.Session()

    if url_parts.scheme == "https":
        # Adapter is available, use it regardless of Python version. Mount on
        # scheme://host without the port so a same-resource redirect that drops
        # the explicit :443 (see do_request) still resolves through the pinned IP.
        base_url = urlunsplit((url_parts.scheme, url_parts.hostname or url_parts.netloc, "", "", ""))
        session.mount(base_url, ForcedIPHTTPSAdapter(dest_ip=ip))
    else:
        # Fall back to old hack-ip-into-url behavior, for either https with no adapter, or http.
        if ip:
            try:
                addr = ipaddress.ip_address(ip)
            except ValueError:
                # Not a valid IP address, so don't try to hack it into the URL
                pass
            else:
                url_parts = url_parts._replace(netloc=f"[{ip}]") if addr.version == 6 else url_parts._replace(netloc=ip)

            uri = urlunsplit([url_parts.scheme, url_parts.netloc, url_parts.path, url_parts.query, url_parts.fragment])

    body_mimetypes = {"openkat-http/body"}
    response = do_request(hostname, session, uri, useragent)

    if "content-type" in response.headers:
        content_type = response.headers["content-type"]

        if content_type in ALLOWED_CONTENT_TYPES:
            body_mimetypes.add(content_type)

        # Pick up the content type for the body from the server and split away encodings to make normalization easier
        content_type_splitted = content_type.split(";")
        if content_type_splitted[0] in ALLOWED_CONTENT_TYPES:
            body_mimetypes.add(content_type_splitted[0])

    har = json.dumps(create_har_object(response))

    return [
        ({"application/json+har"}, har.encode()),
        ({"openkat-http/headers"}, json.dumps(dict(response.headers))),
        (body_mimetypes, response.content),
    ]


def do_request(hostname: str, session: Session, uri: str, useragent: str):
    headers = {"Host": hostname, "User-Agent": useragent}
    response = session.get(uri, headers=headers, verify=False, allow_redirects=False)

    # Follow a redirect only when it points back to the same resource — the
    # server canonicalising the URL (e.g. dropping the explicit :443, or a
    # cache/security warm-up that 301s "/" to itself). Without this the HAR
    # captures an empty redirect body and every body-based analysis (Wappalyzer
    # CMS/tech detection, image extraction) sees nothing. A redirect to a
    # *different* URL (apex->www, http->https, /->/other) is deliberately left
    # as a 301: the oois_in_headers bit turns its Location into a URL that is
    # discovered and scanned as its own resource, so following it here would
    # only duplicate that detection onto the wrong resource.
    seen = {uri}
    while response.is_redirect and len(seen) <= MAX_SAME_RESOURCE_REDIRECTS:
        location = response.headers.get("location")
        if not location:
            break

        target = urljoin(response.url, location)
        if target in seen or not is_same_resource(uri, target):
            break

        seen.add(target)
        response = session.get(target, headers=headers, verify=False, allow_redirects=False)

    return response


def is_same_resource(url: str, other: str) -> bool:
    left, right = urlparse(url), urlparse(other)

    def port(parts):
        return parts.port or DEFAULT_PORTS.get(parts.scheme)

    return (
        left.scheme == right.scheme
        and left.hostname == right.hostname
        and port(left) == port(right)
        and (left.path or "/") == (right.path or "/")
    )


def get_uri(input_: dict) -> str:
    port = f":{input_['web_url']['port']}"
    netloc = (
        input_["web_url"]["netloc"]["address"]
        if "address" in input_["web_url"]["netloc"]
        else input_["web_url"]["netloc"]["name"]
    )
    uri = f"{input_['web_url']['scheme']}://{netloc}{port}{input_['web_url']['path']}"

    return uri
