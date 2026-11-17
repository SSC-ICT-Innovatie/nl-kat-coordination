import json
import math
from os import getenv

import requests
from pybinaryedge import BinaryEdge

from boefjes.plugins.helpers import is_request_timeout, set_session_timeout

DEFAULT_TIMEOUT = 30


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    be = BinaryEdge(getenv("BINARYEDGE_API"))
    results: dict[str, list] = {"results": []}

    input_ = boefje_meta["arguments"]["input"]

    # pybinaryedge does not expose a request timeout; inject one into the
    # session its client uses. Can be overridden through the plugin settings,
    # see schema.json.
    set_session_timeout(be.requests, int(getenv("TIMEOUT", str(DEFAULT_TIMEOUT))))

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

        # iterate through partial results
        page_counter = 0
        total_pages = 1  # set real value after first request

        try:
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
