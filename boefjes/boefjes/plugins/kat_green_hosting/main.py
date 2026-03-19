import requests

API_URL = "https://admin.thegreenwebfoundation.org"


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]
    hostname = input_["hostname"]["name"]

    response = requests.get(f"{API_URL}/greencheck/{hostname}", timeout=30)

    return [(set(), response.content)]
