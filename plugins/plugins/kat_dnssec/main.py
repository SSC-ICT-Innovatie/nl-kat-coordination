import json
import os
import sys

import httpx


def run(file_id: str) -> list[dict[str, str]]:
    token = os.getenv("OPENKAT_TOKEN")
    if not token:
        raise Exception("No OPENKAT_TOKEN env variable")

    base_url = os.getenv("OPENKAT_API")
    if not base_url:
        raise Exception("No OPENKAT_API env variable")

    headers = {"Authorization": "Token " + token}
    client = httpx.Client(base_url=base_url, headers=headers)
    file_content = client.get(f"/file/{file_id}/download/").raise_for_status().content.decode()

    # Find the last status line (not just the last non-comment line)
    for result_line in reversed(file_content.splitlines()):
        if result_line.startswith(("[U]", "[S]", "[B]", "[T]")):
            domain = result_line.split("\t")[0].split(" ")[1].rstrip(".")
            break
    else:
        raise ValueError("No status line found in drill output")

    # [S] self sig OK; [B] bogus; [T] trusted; [U] unsigned
    if result_line.startswith("[U]"):
        finding = {"hostname": domain, "finding_type_code": "KAT-NO-DNSSEC"}
        client.post("/objects/finding/", json=[finding])
        client.delete(f"/objects/finding/KAT-INVALID-DNSSEC|internet|{domain}/")

        return [finding]
    elif result_line.startswith("[S]") or result_line.startswith("[B]"):
        finding = {"hostname": domain, "finding_type_code": "KAT-INVALID-DNSSEC"}
        client.post("/objects/finding/", json=[finding])
        client.delete(f"/objects/finding/KAT-NO-DNSSEC|internet|{domain}/")

        return [finding]

    return []


if __name__ == "__main__":
    result = run(sys.argv[1])
    print(json.dumps(result))  # noqa: T201
