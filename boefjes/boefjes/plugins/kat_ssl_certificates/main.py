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

    # Every input is attempted: a service on any port may do TLS. openssl
    # exits non-zero when the handshake fails, but its output is the
    # observation either way — the chain on success, the reason (no TLS,
    # handshake failure, tcpwrapped) on failure. The normalizer reads the
    # PEM blocks and treats their absence as "nothing to observe"; a task
    # failure would only cause pointless retries against a service that
    # simply does not do TLS.
    #
    # The timeout catches silent blackholes (no SYN-ACK, no response at
    # all): without it, s_client hangs forever and the worker never
    # completes.
    try:
        output = subprocess.run(cmd, capture_output=True, timeout=BOEFJE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as e:
        return [({"openkat/ssl-certificates-output"}, (e.stdout or b"").decode(errors="replace"))]

    return [({"openkat/ssl-certificates-output"}, output.stdout.decode(errors="replace"))]
