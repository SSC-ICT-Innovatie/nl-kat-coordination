import ipaddress
import json
from os import getenv
from urllib.parse import urlparse, urlunparse

import requests
from forcediphttpsadapter.adapters import ForcedIPHTTPSAdapter
from requests import Session
from requests.models import Response

from boefjes.plugins.helpers import get_connect_and_read_timeout, is_request_timeout

ALLOWED_REDIRECT_STATUSES = [301, 302, 307, 308]


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]
    hostname = input_["hostname"]["name"]
    scheme = input_["ip_service"]["service"]["name"]
    ip = input_["ip_service"]["ip_port"]["address"]["address"]

    useragent = getenv("USERAGENT", default="OpenKAT")
    timeout = get_connect_and_read_timeout()
    session = requests.Session()

    results = {}

    for path in [".well-known/security.txt", "security.txt"]:
        uri = f"{scheme}://{hostname}/{path}"

        if scheme == "https":
            session.mount(uri, ForcedIPHTTPSAdapter(dest_ip=ip))
        else:
            addr = ipaddress.ip_address(ip)
            netloc = f"[{ip}]" if addr.version == 6 else ip

            uri = f"{scheme}://{netloc}/{path}"

        try:
            response = do_request(hostname, session, uri, useragent, timeout)

            # if the response is 200, return the content
            if response.status_code == 200:
                results[path] = {"content": response.content.decode(), "url": response.url, "ip": ip, "status": 200}
            # if the response is 301, we need to follow the location header to the correct security txt,
            # we can not force the ip anymore
            elif response.status_code in [301, 302, 307, 308]:
                # Redirect can be absolute or relative
                parsed = urlparse(response.headers["Location"])
                scheme = parsed.scheme if parsed.scheme else scheme
                netloc = parsed.netloc if parsed.netloc else hostname
                uri = urlunparse((scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))

                response = requests.get(uri, stream=True, timeout=timeout, verify=False)  # noqa: S501
                if response.raw._connection:
                    ip = response.raw._connection.sock.getpeername()[0]
                else:
                    ip = ""
                results[path] = {
                    "content": response.content.decode(),
                    "url": response.url,
                    "ip": str(ip),
                    "status": response.status_code,
                }
            else:
                results[path] = {"content": None, "url": None, "ip": None, "status": response.status_code}
        except requests.exceptions.RequestException as exc:
            # Deliberately narrow: only a genuine timeout (including the
            # ConnectionError-wrapped streamed read timeout) is reported as
            # error/timeout; refused connections and DNS failures surface as
            # error/boefje.
            if is_request_timeout(exc):
                return [({"error/timeout"}, f"Requesting security.txt timed out for {hostname}: {type(exc).__name__}")]
            raise

    return [(set(), json.dumps(results))]


def do_request(hostname: str, session: Session, uri: str, useragent: str, timeout: tuple[int, int]) -> Response:
    response = session.get(
        uri, headers={"Host": hostname, "User-Agent": useragent}, verify=False, allow_redirects=False, timeout=timeout
    )

    return response
