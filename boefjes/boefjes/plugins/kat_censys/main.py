import json

from censys.search import CensysHosts


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    h = CensysHosts()
    input_ = boefje_meta["arguments"]["input"]
    ip = input_["address"]
    host = h.view(ip)

    return [(set(), json.dumps(host))]
