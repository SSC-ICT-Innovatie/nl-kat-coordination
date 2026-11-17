from os import getenv

import requests

from boefjes.plugins.helpers import get_connect_and_read_timeout, is_request_timeout


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    cve_id = boefje_meta["arguments"]["input"]["id"]
    cveapi_url = getenv("CVEAPI_URL", "https://cveapi.librekat.nl/v1")
    try:
        response = requests.get(f"{cveapi_url}/{cve_id}.json", timeout=get_connect_and_read_timeout())
    except requests.exceptions.RequestException as exc:
        # Deliberately narrow: only a genuine timeout (including the wrapped
        # body-read variant) is error/timeout; other failures propagate.
        if is_request_timeout(exc):
            return [({"error/timeout"}, f"Request to the CVE API timed out for {cve_id}: {type(exc).__name__}")]
        raise

    return [(set(), response.content)]
