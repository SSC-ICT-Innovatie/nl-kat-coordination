import json
from os import getenv

import requests
from censys.search import CensysHosts

from boefjes.plugins.helpers import is_request_timeout

DEFAULT_TIMEOUT = 30


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    # Can be overridden through the plugin settings, see schema.json.
    h = CensysHosts(timeout=int(getenv("TIMEOUT", str(DEFAULT_TIMEOUT))))
    input_ = boefje_meta["arguments"]["input"]
    ip = input_["address"]
    try:
        host = h.view(ip)
    except requests.exceptions.RequestException as exc:
        # Deliberately narrow: only a genuine timeout (including the wrapped
        # body-read variant) is error/timeout; other failures propagate.
        if is_request_timeout(exc):
            return [({"error/timeout"}, f"Request to Censys timed out for {ip}")]
        raise

    return [(set(), json.dumps(host))]
