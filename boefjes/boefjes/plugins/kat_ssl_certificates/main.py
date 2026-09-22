import subprocess


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]
    hostname = input_["hostname"]["name"]
    scheme = input_["ip_service"]["service"]["name"]
    ip_address = input_["ip_service"]["ip_port"]["address"]["address"]
    port = input_["ip_service"]["ip_port"]["port"]

    if scheme != "https":
        return [({"openkat/deschedule"}, "Skipping check due to non-TLS scheme")]

    cmd = (
        ["/usr/bin/openssl"]
        + boefje_meta["arguments"]["oci_arguments"]
        + ["-host", ip_address, "-port", port, "-servername", hostname]
    )

    output = subprocess.run(cmd, capture_output=True)

    # openssl exits non-zero when the TLS handshake fails (e.g. rc4.badssl.com),
    # but still prints the received certificate chain. That output is valid and
    # should be normalized. Only when no certificates were received is the
    # failure transient (unreachable host, timeout): crash the task so the
    # scheduler retries instead of normalizing an empty result.
    if output.returncode != 0 and b"-----BEGIN CERTIFICATE-----" not in output.stdout:
        output.check_returncode()

    return [({"openkat/ssl-certificates-output"}, output.stdout.decode())]
