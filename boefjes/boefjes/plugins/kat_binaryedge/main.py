import json
import math
from os import getenv

import requests
from pybinaryedge import BinaryEdge
from pybinaryedge.api import BinaryEdgeException, BinaryEdgeNotFound

from boefjes.plugins.helpers import is_request_timeout

DEFAULT_TIMEOUT = 30


class TimeoutBinaryEdge(BinaryEdge):
    """pybinaryedge 0.5 calls requests.get() without a timeout and has no session
    to mount an adapter on, so bound its one request method here."""

    def __init__(self, key: str | None, timeout: int):
        super().__init__(key)
        self.timeout = timeout

    def _get(self, url, params=None):
        headers = {"X-Key": self.key, "User-Agent": self.ua}
        r = requests.get(self.base_url + url, params=params or {}, headers=headers, timeout=self.timeout)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            raise BinaryEdgeNotFound()
        raise BinaryEdgeException(f"Invalid return code {r.status_code}")


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    # Can be overridden through the plugin settings, see schema.json.
    be = TimeoutBinaryEdge(getenv("BINARYEDGE_API"), int(getenv("TIMEOUT", str(DEFAULT_TIMEOUT))))
    results: dict[str, list] = {"results": []}

    input_ = boefje_meta["arguments"]["input"]

    if input_["object_type"] in ["IPAddressV4", "IPAddressV6"]:
        ip = input_["address"]
        try:
            result = be.host(ip)
        except requests.exceptions.RequestException as exc:
            # Deliberately narrow: only a genuine timeout (including the wrapped
            # body-read variant) is error/timeout; other failures propagate.
            if is_request_timeout(exc):
                return [({"error/timeout"}, f"Request to BinaryEdge timed out for {ip}")]
            raise

        # create same result-structure as netblock
        for event in result["events"]:
            results["results"].extend(event["results"])
    elif input_["object_type"] in ["IPV4NetBlock", "IPV6NetBlock"]:
        netblock = input_["mask"]
        dork = f'ip:"{netblock}"'
        try:
            page_counter = 0
            total_pages = 1  # set real value after first request

            while page_counter < total_pages:
                page_counter += 1
                result = be.host_search(dork, page_counter)

                # calculate number of existing pages
                if page_counter == 1:
                    total_pages = math.ceil(result["total"] / result["pagesize"])

                results["results"].extend(result["events"])
        except requests.exceptions.RequestException as exc:
            # Deliberately narrow: only a genuine timeout (including the wrapped
            # body-read variant) is error/timeout; other failures propagate.
            if is_request_timeout(exc):
                return [({"error/timeout"}, f"Request to BinaryEdge timed out for {netblock}")]
            raise

    return [(set(), json.dumps(results))]
