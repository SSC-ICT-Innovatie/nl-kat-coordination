from ipaddress import ip_address

import httpx

REQUEST_TIMEOUT = 60


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    """Make request to InternetDB."""
    ip = boefje_meta["arguments"]["input"]["address"]
    if ip_address(ip).is_private:
        return [({"info/boefje"}, "Skipping private IP address")]
    response = httpx.get(f"https://internetdb.shodan.io/{ip}", timeout=REQUEST_TIMEOUT)
    if response.status_code != httpx.codes.NOT_FOUND:
        response.raise_for_status()

    return [(set(), response.content)]
