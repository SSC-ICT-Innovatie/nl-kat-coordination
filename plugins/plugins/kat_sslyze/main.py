import argparse
import os

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
            server_location=sslyze.ServerNetworkLocation(hostname, 443),
            scan_commands={
                ScanCommand.CERTIFICATE_INFO,
                ScanCommand.TLS_EXTENDED_MASTER_SECRET,
                ScanCommand.HTTP_HEADERS,
                ScanCommand.TLS_FALLBACK_SCSV,
                ScanCommand.TLS_1_0_CIPHER_SUITES,
                ScanCommand.TLS_1_1_CIPHER_SUITES,
                ScanCommand.TLS_1_2_CIPHER_SUITES,
                ScanCommand.TLS_1_3_CIPHER_SUITES,
                ScanCommand.SSL_2_0_CIPHER_SUITES,
                ScanCommand.SSL_3_0_CIPHER_SUITES,
            },
        )
        for hostname in args.hostnames
    ]

    scanner = sslyze.Scanner()
    scanner.queue_scans(all_scan_requests)

    findings: list[dict] = []

    for server_scan_result in scanner.get_results():
        hostname = server_scan_result.server_location.hostname
        if server_scan_result.scan_status != sslyze.ServerScanStatusEnum.COMPLETED:
            continue

        scan_command = server_scan_result.scan_result

        # check for invalid certs
        # check for invalid certs
        codes = []
        for cert in scan_command.certificate_info.result.certificate_deployments:
            if any(not x.was_validation_successful for x in cert.path_validation_results):
                codes.append("KAT-CERTIFICATE-EXPIRED")

        # check for missing extensions
        if not scan_command.tls_extended_master_secret.result.supports_ems_extension:
            codes.append("KAT-EMS-NOT-SUPPORTED")

        # check for missing HSTS
        if scan_command.http_headers.result.strict_transport_security_header is None:
            codes.append("KAT-NO-HSTS")

        # check for downgrade prevention
        if not scan_command.tls_fallback_scsv.result.supports_fallback_scsv:
            codes.append("KAT-NO-TLS-FALLBACK-SCSV")

        # check for supported/unsupported TLS versions
        if scan_command.tls_1_0_cipher_suites.result.is_tls_version_supported:
            codes.append("KAT-TLS-1.0-SUPPORT")
        if scan_command.tls_1_1_cipher_suites.result.is_tls_version_supported:
            codes.append("KAT-TLS-1.1-SUPPORT")
        if not scan_command.tls_1_2_cipher_suites.result.is_tls_version_supported:
            codes.append("KAT-NO-TLS-1.2")
        if not scan_command.tls_1_3_cipher_suites.result.is_tls_version_supported:
            codes.append("KAT-NO-TLS-1.3")
        if scan_command.ssl_2_0_cipher_suites.result.is_tls_version_supported:
            codes.append("KAT-SSL-2-SUPPORT")
        if scan_command.ssl_3_0_cipher_suites.result.is_tls_version_supported:
            codes.append("KAT-SSL-3-SUPPORT")

        findings.extend({"finding_type_code": code, "hostname": hostname} for code in codes)

    client.post("/objects/finding/", json=findings).raise_for_status()


if __name__ == "__main__":
    main()
