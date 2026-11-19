import requests

from boefjes.plugins.helpers import get_connect_and_read_timeout, is_request_timeout

API_URL = "https://admin.thegreenwebfoundation.org"


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]
    hostname = input_["hostname"]["name"]

    try:
        response = requests.get(f"{API_URL}/greencheck/{hostname}", timeout=get_connect_and_read_timeout())
    except requests.exceptions.RequestException as exc:
        # Deliberately narrow: only a genuine timeout (including the wrapped
        # body-read variant) is error/timeout; other failures propagate.
        if is_request_timeout(exc):
            return [
                (
                    {"error/timeout"},
                    f"Request to thegreenwebfoundation.org timed out for {hostname}: {type(exc).__name__}",
                )
            ]
        raise

    return [(set(), response.content)]
