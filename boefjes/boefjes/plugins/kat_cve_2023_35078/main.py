from urllib.parse import urljoin

import requests

from boefjes.plugins.helpers import get_connect_and_read_timeout, is_request_timeout

ENDPOINT_PATH = "/mifs/c/windows/api/v2/device/registration"


def run(boefje_meta: dict) -> list[tuple[set, str | bytes]]:
    input_ = boefje_meta["arguments"]["input"]  # input is website
    hostname = input_["hostname"]["name"]
    service = input_["ip_service"]["service"]["name"]
    website = f"{service}://{hostname}"

    full_url = urljoin(website, ENDPOINT_PATH)
    try:
        response = requests.get(full_url, verify=False, allow_redirects=False, timeout=get_connect_and_read_timeout())  # noqa: S501
    except requests.exceptions.RequestException as exc:
        # Deliberately narrow: only a genuine timeout (including the wrapped
        # body-read variant) is error/timeout; other failures propagate.
        if is_request_timeout(exc):
            return [
                (
                    {"error/timeout"},
                    f"Ivanti Endpoint Manager Mobile (EPMM) check timed out for {hostname}: {type(exc).__name__}",
                )
            ]
        raise

    if response.status_code == 200:
        return [(set(), response.content)]
    else:
        return [(set(), "Ivanti Endpoint Manager Mobile (EPMM), formerly MobileIron Core not found")]
