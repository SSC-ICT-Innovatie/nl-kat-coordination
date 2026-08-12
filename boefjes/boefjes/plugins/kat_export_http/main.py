"""Boefje script for exporting OOI's to an external http api"""

import json
from os import getenv
from typing import Any

import requests


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ooi = boefje_meta["arguments"]["input"]

    timeout = getenv("TIMEOUT", default=15)
    endpoint_uri = getenv("EXPORT_HTTP_ENDPOINT", "")
    request_headers = getenv("EXPORT_REQUEST_HEADERS", "")
    request_parameter = getenv("EXPORT_REQUEST_PARAMETER", "")
    request_verb = getenv("EXPORT_HTTP_VERB", default="POST").lower()
    useragent = getenv("USERAGENT", default="OpenKAT")
    organization = getenv("", boefje_meta["organization"])

    headers = {"User-Agent": useragent}

    request_header_list = request_headers.split("\n")
    headers.update({header.split(":")[0]: header.split(":")[1] for header in request_header_list if ":" in header})

    kwargs: dict[str, Any] = {"headers": headers, "timeout": float(timeout)}

    if request_verb == "get":
        kwargs.update({"params": {request_parameter: json.dumps(input_ooi), "organization": organization}})
    else:
        if request_parameter:
            kwargs.update({"data": {request_parameter: json.dumps(input_ooi), "organization": organization}})
        else:
            kwargs.update({"json": input_ooi})

    response = requests.request(request_verb, endpoint_uri, **kwargs)  # noqa: S113
    response.raise_for_status()

    return [(set(), response.content)]
