"""Boefje script for getting domains and ipaddresses from dadb"""

from os import getenv

import requests


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    """Fetch external database response."""
    api_format = getenv(
        "DB_ENDPOINT_FORMAT",
        "{DB_URL}/api/v1/organizations/assets/{DB_ORGANIZATION_IDENTIFIER}?access_token={DB_ACCESS_TOKEN}",
    )
    request_timeout = 100

    get_request = api_format.format(
        DB_URL=getenv("DB_URL"),
        DB_ORGANIZATION_IDENTIFIER=getenv("DB_ORGANIZATION_IDENTIFIER", boefje_meta["organization"]),
        DB_ACCESS_TOKEN=getenv("DB_ACCESS_TOKEN", ""),
    )
    response = requests.get(get_request, timeout=request_timeout)
    if not response.ok:
        raise ValueError(response.content)

    return [(set(), response.content)]
