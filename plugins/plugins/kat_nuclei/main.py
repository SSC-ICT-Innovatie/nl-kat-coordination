import json
import os
import sys
from collections import defaultdict
from json import JSONDecodeError

import httpx


def run(file_id: str) -> dict[str, list] | None:
    token = os.getenv("OPENKAT_TOKEN")
    if not token:
        raise Exception("No OPENKAT_TOKEN env variable")

    base_url = os.getenv("OPENKAT_API")
    if not base_url:
        raise Exception("No OPENKAT_API env variable")

    headers = {"Authorization": "Token " + token}
    client = httpx.Client(base_url=base_url, headers=headers)

    file = client.get(f"/file/{file_id}/download/")

    results_grouped = defaultdict(list)

    for line in file.content.decode().split("\n"):
        if not line.strip():
            continue

        try:
            info = json.loads(line.strip())
        except JSONDecodeError as e:
            raise ValueError(f"Invalid json in line: {line}") from e

        try:
            if info["template-id"].endswith("-detect"):
                software = info["template-id"].rstrip("-detect")
            elif info["template-id"] == "ibm-d2b-database-server":
                software = "db2"
            else:
                continue  # template id not recognized

            results_grouped["ipaddress"].append({"address": info["ip"], "network": "internet"})
            results_grouped["ipport"].append(
                {
                    "address": info["ip"],
                    "protocol": info["type"].upper(),
                    "port": int(info["port"]),
                    "service": software,
                    "software": [{"name": software}],
                }
            )
        except KeyError as e:
            raise ValueError(f"Invalid info line in output: {info}") from e

    if not results_grouped["ipaddress"]:
        return None

    client.post("/objects/", headers=headers, json=results_grouped).raise_for_status()

    return results_grouped


if __name__ == "__main__":
    results = run(sys.argv[1])

    print(json.dumps(results))  # noqa: T201
