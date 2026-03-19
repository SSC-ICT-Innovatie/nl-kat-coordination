from urllib.parse import urljoin

import requests

ENDPOINT_PATH = "/mifs/c/windows/api/v2/device/registration"


def run(boefje_meta: dict) -> list[tuple[set, str | bytes]]:
    input_ = boefje_meta["arguments"]["input"]  # input is website
    hostname = input_["hostname"]["name"]
    service = input_["ip_service"]["service"]["name"]
    website = f"{service}://{hostname}"

    full_url = urljoin(website, ENDPOINT_PATH)
    response = requests.get(full_url, verify=False, allow_redirects=False, timeout=30)  # noqa: S501

    if response.status_code == 200:
        return [(set(), response.content)]
    else:
        return [(set(), "Ivanti Endpoint Manager Mobile (EPMM), formerly MobileIron Core not found")]
