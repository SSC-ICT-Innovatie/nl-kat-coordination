import argparse
import os

import httpx
from securitytxt import SecurityTXT


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
        try:
            sec = SecurityTXT.from_url(hostname)
        except FileNotFoundError:
            findings.append({"finding_type_code": "KAT-NO-SECURITY-TXT", "hostname": hostname})
        else:
            if not sec.is_valid():
                findings.append({"finding_type_code": "KAT-INVALID-SECURITY-TXT", "hostname": hostname})
            if not sec.required_fields_present():
                findings.append({"finding_type_code": "KAT-BAD-FORMAT-SECURITY-TXT", "hostname": hostname})

    client.post("/objects/finding/", json=findings).raise_for_status()


if __name__ == "__main__":
    main()
