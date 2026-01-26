import json
from os import getenv
from urllib.parse import quote_plus

import requests

API_TIMEOUT = 30


def get_api_headers() -> dict:
    """Get API headers with current LEAKIX_API key."""
    return {"Accept": "application/json", "api-key": getenv("LEAKIX_API", "")}


def get_host_results(ip: str) -> list[dict]:
    """Use /host/{ip} endpoint for specific IP lookups (no netblock pollution)."""
    results: list[dict] = []
    response = requests.get(f"https://leakix.net/host/{ip}", headers=get_api_headers(), timeout=API_TIMEOUT)
    if not response or not response.content:
        return results

    response_json = response.json()
    if not response_json:
        return results

    # /host endpoint returns {"Services": [...], "Leaks": [...]}
    # Convert to same format as /search for normalizer compatibility
    for service in response_json.get("Services") or []:
        if service.get("event_fingerprint"):
            results.append(service)

    for leak in response_json.get("Leaks") or []:
        if leak.get("event_fingerprint"):
            results.append(leak)

    return results


def get_search_results(query: str) -> list[dict]:
    """Use /search endpoint for hostname lookups (filtered in normalizer)."""
    results: list[dict] = []
    for scope in ("leak", "service"):
        page_counter = 0
        want_next_result = True
        while want_next_result:
            want_next_result = False
            response = requests.get(
                f"https://leakix.net/search?scope={scope}&q={query}&page={page_counter}",
                headers=get_api_headers(),
                timeout=API_TIMEOUT,
            )
            page_counter += 1
            if not response or not response.content:
                break
            response_json = response.json()
            if not response_json:
                break

            for event in response_json:
                if not event.get("event_fingerprint"):
                    continue
                want_next_result = True
                results.append(event)

    return results


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    pk = boefje_meta["input_ooi"]
    if not pk:
        raise Exception("LeakIX boefje requires an input OOI")

    search_mode = getenv("LEAKIX_SEARCH_MODE", "strict")

    if pk.startswith("IPAddressV4|") or pk.startswith("IPAddressV6|"):
        ip = pk.split("|")[-1]
        if search_mode == "strict":
            # Use /host endpoint for exact IP match (no netblock pollution)
            results = get_host_results(ip)
        else:
            # Permissive mode: use /search (may include related IPs in netblock)
            query = quote_plus(f"+ip:{ip}")
            results = get_search_results(query)
    elif pk.startswith("Hostname|"):
        hostname = pk.split("|")[-1]
        query = quote_plus(f'+host:"{hostname}"')
        results = get_search_results(query)
        # Filtering for hostname happens in normalizer based on search_mode
    else:
        raise NameError(f'Expected an IPAddress or Hostname, but got pk "{pk}"')

    # Include search_mode in output so normalizer can filter accordingly
    output = {"search_mode": search_mode, "input_ooi": pk, "results": results}

    return [(set(), json.dumps(output))]
