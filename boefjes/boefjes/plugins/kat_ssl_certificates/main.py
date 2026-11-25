import subprocess

BOEFJE_TIMEOUT_SECONDS = 30


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]

    if input_["object_type"] == "IPService":
        # A bare IPService: connect without a server name. The presentation
        # is valid for the null server name only.
        hostname = None
    else:
        # Website (legacy) and HostnameIPService inputs carry a hostname:
        # connect for that server name.
        hostname = input_["hostname"]["name"]

    ip_address = input_["ip_service"]["ip_port"]["address"]["address"]
    port = int(input_["ip_service"]["ip_port"]["port"])

    # openssl s_client -host takes the bare address: bracketed IPv6 makes
    # BIO_lookup_ex fail with "Name or service not known" (verified against
    # OpenSSL 3.5.7).
    host = ip_address
    server_name_args = ["-servername", hostname] if hostname else []

    cmd = (
        ["/usr/bin/openssl"]
        + boefje_meta["arguments"]["oci_arguments"]
        + ["-host", host, "-port", str(port)]
        + server_name_args
    )

    # Every input is attempted: a service on any port may do TLS. The
    # output's mime type carries the meaning, per the established
    # error-code vocabulary:
    #   error/timeout  — the connection or handshake exceeded the timeout
    #                    (rerunnable; distinct task state per #5553)
    #   error/boefje   — the connection itself failed (refused, unreachable,
    #                    DNS failure); surfaces as a task failure
    #   info/boefje    — the service answered but presented no certificate
    #                    (no TLS, tcpwrapped); expected and non-actionable,
    #                    the normalizer is skipped
    #   openkat/ssl-certificates-output — the presentation itself
    #
    # The timeout catches silent blackholes (no SYN-ACK, no response at
    # all): without it, s_client hangs forever and the worker never
    # completes.
    try:
        output = subprocess.run(cmd, capture_output=True, timeout=BOEFJE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as e:
        partial = (e.stdout or b"").decode(errors="replace")
        message = f"TLS handshake with {host}:{port} timed out after {BOEFJE_TIMEOUT_SECONDS}s"
        return [({"error/timeout"}, f"{message}\n{partial}".strip())]

    if b"-----BEGIN CERTIFICATE-----" not in output.stdout:
        combined = (output.stderr or b"") + (output.stdout or b"")
        if b"connect:" in combined or b"Connection refused" in combined or b"Network is unreachable" in combined:
            # The TCP connection itself failed: a task failure with the
            # reason in Bytes, and no normalization (nothing previously
            # observed gets deleted).
            return [({"error/boefje"}, combined.decode(errors="replace").strip())]

        # The TCP connection succeeded but no certificate was presented:
        # no TLS on this service, or it closed the connection (tcpwrapped).
        # Expected and non-actionable: the normalizer is skipped.
        reason = (output.stderr or output.stdout or b"no response").decode(errors="replace").strip()
        return [({"info/boefje"}, f"No certificate presented by {host}:{port}\n{reason}".strip())]

    return [({"openkat/ssl-certificates-output"}, output.stdout.decode(errors="replace"))]
