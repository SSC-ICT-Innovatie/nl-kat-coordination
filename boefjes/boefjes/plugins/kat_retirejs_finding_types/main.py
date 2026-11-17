import requests

from boefjes.plugins.helpers import get_connect_and_read_timeout, is_request_timeout


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    try:
        response = requests.get(
            "https://raw.githubusercontent.com/RetireJS/retire.js/v3/repository/jsrepository.json",
            timeout=get_connect_and_read_timeout(),
        )
    except requests.exceptions.RequestException as exc:
        # Deliberately narrow: only a genuine timeout (including the wrapped
        # body-read variant) is error/timeout; other failures propagate.
        if is_request_timeout(exc):
            return [({"error/timeout"}, f"Downloading the RetireJS repository timed out: {type(exc).__name__}")]
        raise

    return [(set(), response.content)]
