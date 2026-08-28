import json

FINDING_TYPE_PATH = "boefjes/plugins/kat_adr_finding_types/adr_finding_types.json"


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    with open(FINDING_TYPE_PATH) as json_file:
        data = json.load(json_file)
        return [(set(), json.dumps(data))]
