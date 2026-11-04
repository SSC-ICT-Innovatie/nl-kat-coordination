import subprocess
from ipaddress import ip_address as parse_ip


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

    scheme = input_["ip_service"]["service"]["name"]
    ip_address = input_["ip_service"]["ip_port"]["address"]["address"]
    port = int(input_["ip_service"]["ip_port"]["port"])

    if scheme != "https":
        # TODO: this check is wrong in general (smtps, imaps, ... also do
        # TLS); revisit with the STARTTLS/implicit-TLS work.
        return [({"openkat/deschedule"}, "Skipping check due to non-TLS scheme")]

    # openssl s_client -host does not accept bare IPv6 addresses; wrap them in brackets
    host = f"[{ip_address}]" if parse_ip(ip_address).version == 6 else ip_address
    server_name_args = ["-servername", hostname] if hostname else []

    cmd = (
        ["/usr/bin/openssl"]
        + boefje_meta["arguments"]["oci_arguments"]
        + ["-host", host, "-port", str(port)]
        + server_name_args
    )

    output = subprocess.run(cmd, capture_output=True)

    # openssl exits non-zero when the TLS handshake fails (e.g. rc4.badssl.com),
    # but still prints the received certificate chain. That output is valid and
    # should be normalized. Only when no certificates were received is the
    # failure transient (unreachable host, timeout): crash the task so the
    # scheduler retries instead of normalizing an empty result.
    if output.returncode != 0 and b"-----BEGIN CERTIFICATE-----" not in output.stdout:
        output.check_returncode()

    return [({"openkat/ssl-certificates-output"}, output.stdout.decode(errors="replace"))]
