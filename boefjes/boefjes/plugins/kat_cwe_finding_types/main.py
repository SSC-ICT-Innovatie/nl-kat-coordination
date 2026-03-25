import json

import defusedxml.ElementTree as ET

FINDING_TYPE_PATH = "boefjes/plugins/kat_cwe_finding_types/cwec_v4.16.xml"


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    cwe_id = boefje_meta["arguments"]["input"]["id"]

    root = ET.parse(FINDING_TYPE_PATH)
    root = root.getroot()

    # Define the XML namespace
    namespace = {"ns": "http://cwe.mitre.org/cwe-7"}

    # Find the Weakness element with the specified CWE ID
    xpath = f".//ns:Weakness[@ID='{cwe_id.split('-')[1]}']"
    weakness_elem = root.find(xpath, namespace)

    # Retrieve the name and description
    name = weakness_elem.get("Name")
    description = weakness_elem.find("ns:Description", namespace).text

    data = {"name": name, "description": description}

    return [(set(), json.dumps(data))]
