import json
import re

import requests
from bs4 import BeautifulSoup


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    snyk_id = boefje_meta["arguments"]["input"]["id"]
    url_snyk = f"https://snyk.io/vuln/{snyk_id}"
    page = requests.get(url_snyk, timeout=30)
    soup = BeautifulSoup(page.content, "html.parser")
    result = {
        "risk": soup.select("[data-snyk-test-score]")[0].attrs["data-snyk-test-score"],
        "affected_versions": soup.select("[data-snyk-test='vuln versions']")[0].text.strip(),
        "summary": soup.findAll("h2", text=re.compile(r"Overview"))[0].parent.text.strip().split("\n")[2],
    }

    return [(set(), json.dumps(result))]
