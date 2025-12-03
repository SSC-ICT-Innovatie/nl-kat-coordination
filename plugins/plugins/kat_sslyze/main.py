import argparse
import os
import pprint

import httpx
import sslyze
from sslyze import ScanCommand


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

    all_scan_requests = [
        sslyze.ServerScanRequest(
            server_location=sslyze.ServerNetworkLocation(hostname, 443), scan_commands={ScanCommand.CERTIFICATE_INFO}
        )
        for hostname in args.hostnames
    ]

    scanner = sslyze.Scanner()
    scanner.queue_scans(all_scan_requests)

    findings = []

    for server_scan_result in scanner.get_results():
        hostname = server_scan_result.server_location.hostname
        port = server_scan_result.server_location.port
        if server_scan_result.scan_status != sslyze.ServerScanStatusEnum.COMPLETED:
            continue

        # check for invalid certs
        for cert in server_scan_result.scan_result.certificate_info.result.certificate_deployments:
            if any(not x.was_validation_successful for x in cert.path_validation_results):
                findings.append({"finding_type_code": "KAT-CERTIFICATE-EXPIRED", "hostname": hostname})

    pprint.pprint(findings)
    client.post("/objects/finding/", json=findings).raise_for_status()


if __name__ == "__main__":
    main()
