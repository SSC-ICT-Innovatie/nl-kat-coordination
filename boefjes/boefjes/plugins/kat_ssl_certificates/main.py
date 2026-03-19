import subprocess


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]
    hostname = input_["hostname"]["name"]
    scheme = input_["ip_service"]["service"]["name"]
    ip_address = input_["ip_service"]["ip_port"]["address"]["address"]
    port = input_["ip_service"]["ip_port"]["port"]

    if scheme != "https":
        return [({"info/boefje"}, "Skipping check due to non-TLS scheme")]

    cmd = (
        ["/usr/bin/openssl"]
        + boefje_meta["arguments"]["oci_arguments"]
        + ["-host", ip_address, "-port", port, "-servername", hostname]
    )

    output = subprocess.run(cmd, capture_output=True)
    output.check_returncode()

    return [({"openkat/ssl-certificates-output"}, output.stdout.decode())]
