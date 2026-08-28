from ipaddress import ip_address
from os import getenv

import httpx

REQUEST_TIMEOUT = 60


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    """Make request to InternetDB."""
    ip = boefje_meta["arguments"]["input"]["address"]
    if ip_address(ip).is_private:
        return [({"openkat/deschedule"}, "Private IP requested, I will not forward this to Shodan.")]
    response = httpx.get(
        f"https://internetdb.shodan.io/{ip}", timeout=int(getenv("REQUEST_TIMEOUT", str(REQUEST_TIMEOUT)))
    )
    if response.status_code != httpx.codes.NOT_FOUND:
        response.raise_for_status()

    return [(set(), response.content)]
