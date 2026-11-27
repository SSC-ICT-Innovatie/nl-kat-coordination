import json
import re

import requests
from bs4 import BeautifulSoup

from boefjes.plugins.helpers import get_connect_and_read_timeout, is_request_timeout


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    snyk_id = boefje_meta["arguments"]["input"]["id"]
    url_snyk = f"https://snyk.io/vuln/{snyk_id}"
    try:
        page = requests.get(url_snyk, timeout=get_connect_and_read_timeout())
    except requests.exceptions.RequestException as exc:
        # Deliberately narrow: only a genuine timeout (including the wrapped
        # body-read variant) is error/timeout; other failures propagate.
        if is_request_timeout(exc):
            return [({"error/timeout"}, f"Request to snyk.io timed out for {snyk_id}: {type(exc).__name__}")]
        raise
    soup = BeautifulSoup(page.content, "html.parser")
    result = {
        "risk": soup.select("[data-snyk-test-score]")[0].attrs["data-snyk-test-score"],
        "affected_versions": soup.select("[data-snyk-test='vuln versions']")[0].text.strip(),
        "summary": soup.findAll("h2", text=re.compile(r"Overview"))[0].parent.text.strip().split("\n")[2],
    }

    return [(set(), json.dumps(result))]
