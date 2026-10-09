import os
import subprocess
import tempfile
from ipaddress import ip_address
from pathlib import Path

TLS_CAPABLE_SERVICES = ("https", "ftps", "smtps", "imaps", "pops")
STARTTLS_CAPABLE_SERVICES = (
    "ftp",
    "smtp",
    "lmtp",
    "pop3",
    "imap",
    "xmpp",
    "xmpp-server",
    "telnet",
    "ldap",
    "nntp",
    "sieve",
    "irc",
    "postgres",
    "mysql",
)

TESTSSL_BINARY = "/usr/local/bin/testssl.sh"
OUTPUT_MEDIA_TYPE = "openkat/testssl-sh-ciphers-output"


def _input_target(input_: dict) -> tuple[str | None, str, int, str]:
    """Return hostname, address, port and service name from a HostnameService/IPService input."""
    if input_.get("object_type") == "HostnameService":
        ip_service = input_["ip_service"]
        address = ip_service["ip_port"]["address"]["address"]
        port = int(ip_service["ip_port"]["port"])
        servicename = ip_service["service"]["name"]
        hostname = input_.get("hostname", {}).get("name")
        return hostname, address, port, servicename

    # Backwards-compatible input handling for existing IPService scans.
    ip_port = input_["ip_port"]
    address = ip_port["address"]["address"]
    port = int(ip_port["port"])
    servicename = input_["service"]["name"]
    return None, address, port, servicename


def _jsonfile_argument(arguments: list[str], output_path: Path) -> list[str]:
    """Replace the configured JSON output path with a unique per-run path."""
    result = list(arguments)
    for index, argument in enumerate(result):
        if argument == "--jsonfile":
            if index + 1 >= len(result):
                raise ValueError("--jsonfile requires an output path")
            result[index + 1] = str(output_path)
            return result
        if argument.startswith("--jsonfile="):
            result[index] = f"--jsonfile={output_path}"
            return result
    raise ValueError("testssl.sh must be configured with --jsonfile")


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]
    hostname, address, port, servicename = _input_target(input_)

    if servicename not in TLS_CAPABLE_SERVICES + STARTTLS_CAPABLE_SERVICES:
        return [({"openkat/deschedule"}, "Skipping check due to non-TLS/STARTTLS service")]

    timeout = int(os.getenv("TIMEOUT", "30"))
    configured_arguments = boefje_meta["arguments"].get("oci_arguments", [])

    with tempfile.TemporaryDirectory(prefix="testssl-") as temp_dir:
        output_path = Path(temp_dir) / "output.json"
        cmd = [TESTSSL_BINARY] + _jsonfile_argument(configured_arguments, output_path)

        if servicename in STARTTLS_CAPABLE_SERVICES:
            cmd.extend(["--starttls", servicename])
            if servicename in {"xmpp", "xmpp-server"} and hostname:
                cmd.extend(["--xmpphost", hostname])

        # Keep the hostname as the TLS target so testssl sends it as SNI, while
        # --ip forces the TCP connection to the exact IP represented by the OOI.
        if ip_address(address).version == 6:
            cmd.append("-6")

        if hostname:
            cmd.extend(["--ip", f"[{address}]"])

        target = f"{hostname}:{port}" if hostname else f"[{address}]:{port}"
        cmd.append(target)

        env = os.environ.copy()
        env["OPENSSL_TIMEOUT"] = str(timeout)
        env["CONNECT_TIMEOUT"] = str(timeout)

        output = subprocess.run(cmd, capture_output=True, env=env)

        # A non-zero exit is not automatically a discard: testssl can produce a
        # useful JSON report for a partially completed scan. Only fail when no
        # valid JSON artifact was produced.
        if not output_path.exists():
            output.check_returncode()
            raise RuntimeError("testssl.sh completed without producing JSON output")

        raw = output_path.read_bytes()
        if not raw.strip():
            output.check_returncode()
            raise RuntimeError("testssl.sh produced an empty JSON output")

        return [({OUTPUT_MEDIA_TYPE}, raw)]
