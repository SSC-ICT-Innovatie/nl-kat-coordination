import argparse
import os
from pprint import pprint

import httpx
from sectxt import SecurityTXT


def main():
    token = os.getenv("OPENKAT_TOKEN")
    base_url = os.getenv("OPENKAT_API")

    if not token:
        raise Exception("No OPENKAT_TOKEN env variable")
    if not base_url:
        raise Exception("No OPENKAT_API env variable")

    client = httpx.Client(base_url=base_url, headers={"Authorization": "Token " + token})

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("hostnames", nargs="*")
    args = parser.parse_args()

    findings = []

    for hostname in args.hostnames:
        sec = SecurityTXT(hostname)
        if "no_security_txt" in sec.errors:
            findings.append({"finding_type_code": "KAT-NO-SECURITY-TXT", "hostname": hostname})
        if not sec.is_valid():
            findings.append({"finding_type_code": "KAT-INVALID-SECURITY-TXT", "hostname": hostname})
        if "unknown_field" in sec.errors:
            findings.append({"finding_type_code": "KAT-BAD-FORMAT-SECURITY-TXT", "hostname": hostname})

        pprint(sec.errors)  # noqa

    client.post("/objects/finding/", json=findings).raise_for_status()


if __name__ == "__main__":
    main()
