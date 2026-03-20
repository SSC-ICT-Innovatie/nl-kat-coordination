from os import getenv

import requests


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    cve_id = boefje_meta["arguments"]["input"]["id"]
    cveapi_url = getenv("CVEAPI_URL", "https://cveapi.librekat.nl/v1")
    response = requests.get(f"{cveapi_url}/{cve_id}.json", timeout=30)

    return [(set(), response.content)]
