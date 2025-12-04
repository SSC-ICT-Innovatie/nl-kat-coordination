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

    findings = []

    for server_scan_result in scanner.get_results():
        hostname = server_scan_result.server_location.hostname
        if server_scan_result.scan_status != sslyze.ServerScanStatusEnum.COMPLETED:
            continue

        # check for invalid certs
        for cert in server_scan_result.scan_result.certificate_info.result.certificate_deployments:
            if any(not x.was_validation_successful for x in cert.path_validation_results):
                findings.append({"finding_type_code": "KAT-CERTIFICATE-EXPIRED", "hostname": hostname})

        # check for missing extensions
        if not server_scan_result.scan_result.tls_extended_master_secret.result.supports_ems_extension:
            findings.append({"finding_type_code": "KAT-EMS-NOT-SUPPORTED", "hostname": hostname})

        # check for missing HSTS
        if server_scan_result.scan_result.http_headers.result.strict_transport_security_header is None:
            findings.append({"finding_type_code": "KAT-NO-HSTS", "hostname": hostname})

        # check for downgrade prevention
        if not server_scan_result.scan_result.tls_fallback_scsv.result.supports_fallback_scsv:
            findings.append({"finding_type_code": "KAT-NO-TLS-FALLBACK-SCSV", "hostname": hostname})

        # check for supported/unsupported TLS versions
        if server_scan_result.scan_result.tls_1_0_cipher_suites.result.is_tls_version_supported:
            findings.append({"finding_type_code": "KAT-TLS-1.0-SUPPORT", "hostname": hostname})
        if server_scan_result.scan_result.tls_1_1_cipher_suites.result.is_tls_version_supported:
            findings.append({"finding_type_code": "KAT-TLS-1.1-SUPPORT", "hostname": hostname})
        if not server_scan_result.scan_result.tls_1_2_cipher_suites.result.is_tls_version_supported:
            findings.append({"finding_type_code": "KAT-NO-TLS-1.2", "hostname": hostname})
        if not server_scan_result.scan_result.tls_1_3_cipher_suites.result.is_tls_version_supported:
            findings.append({"finding_type_code": "KAT-NO-TLS-1.3", "hostname": hostname})
        if server_scan_result.scan_result.ssl_2_0_cipher_suites.result.is_tls_version_supported:
            findings.append({"finding_type_code": "KAT-SSL-2-SUPPORT", "hostname": hostname})
        if server_scan_result.scan_result.ssl_3_0_cipher_suites.result.is_tls_version_supported:
            findings.append({"finding_type_code": "KAT-SSL-3-SUPPORT", "hostname": hostname})

    client.post("/objects/finding/", json=findings).raise_for_status()


if __name__ == "__main__":
    main()
