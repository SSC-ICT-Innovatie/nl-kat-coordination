import json
from os import getenv

import requests

CRT_SH_API = "https://crt.sh/"
# The timeout consists of two values: a connection timeout and an inactivity (read) timeout.
# Both can be overridden through the plugin settings, see schema.json.
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 30
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

    # The timeout consists of two values, a connection timeout and an inactivity timeout.
    timeout = (int(getenv("CONNECT_TIMEOUT", str(CONNECT_TIMEOUT))), int(getenv("READ_TIMEOUT", str(READ_TIMEOUT))))
    response = requests.get(CRT_SH_API, params=query, timeout=timeout)
    if response.status_code != 200:
        response.raise_for_status()
    if json_output:
        return json.dumps(response.json())
    return response.text


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]
    fqdn = input_["hostname"]["name"]

    try:
        results = request_certs(fqdn)
    except requests.exceptions.Timeout as exc:
        # Deliberately narrow: ConnectTimeout subclasses ConnectionError too, but plain
        # ConnectionError (DNS failure, refused connection) and SSLError are failures,
        # not timeouts, and should surface as error/boefje instead.
        return [({"error/timeout"}, f"crt.sh timed out for {fqdn}: {type(exc).__name__}")]

    return [(set(), results)]
