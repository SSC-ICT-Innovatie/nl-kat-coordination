import json

import requests

CRT_SH_API = "https://crt.sh/"
MATCHES = ("=", "ILIKE", "LIKE", "single", "any", "FTS")
SEARCH_TYPES = (
    "c",
    "id",
    "ctid",
    "serial",
    "ski",
    "spkisha1",
    "spkisha256",
    "subjectsha1",
    "sha1",
    "sha256",
    "ca",
    "CAID",
    "CAName",
    "Identity",
    "CN",
    "E",
    "OU",
    "O",
    "dNSName",
    "rfc822Name",
    "iPAddress",
)


def request_certs(
    search_string: str,
    search_type: str = "Identity",
    match: str = "=",
    deduplicate: bool = True,
    json_output: bool = True,
) -> str:
    """Queries the public service CRT.sh for certificate information
    the searchtype can be specified and defaults to Identity.
    the type of sql matching can be specified and defaults to "="
    Deduplication is on by default and the output is returned as a json string or html.
    """
    if match not in MATCHES:
        match = MATCHES[0]
    if search_type not in SEARCH_TYPES:
        search_type = "Identity"
    query = {search_type: search_string, "match": match}
    if json_output:
        query["output"] = "json"
    if deduplicate:
        query["deduplicate"] = "Y"

    response = requests.get(CRT_SH_API, params=query, timeout=30)
    if response.status_code != 200:
        response.raise_for_status()
    if json_output:
        return json.dumps(response.json())
    return response.text


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]
    fqdn = input_["hostname"]["name"]
    results = request_certs(fqdn)

    return [(set(), results)]
