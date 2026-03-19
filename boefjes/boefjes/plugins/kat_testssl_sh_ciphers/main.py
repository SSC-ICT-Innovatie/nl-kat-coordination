import os
import subprocess
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
    "telnet",
    "ldap",
    "nntp",
    "postgres",
    "mysql",
)


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]
    ip_port = input_["ip_port"]["port"]
    address = input_["ip_port"]["address"]["address"]
    servicename = input_["service"]["name"]

    if servicename not in TLS_CAPABLE_SERVICES + STARTTLS_CAPABLE_SERVICES:
        return [({"info/boefje"}, "Skipping check due to non-TLS/STARTTLS service")]

    cmd = ["/usr/local/bin/testssl.sh"] + boefje_meta["arguments"]["oci_arguments"]

    if servicename in STARTTLS_CAPABLE_SERVICES:
        cmd.extend(["--starttls", servicename])

    if ip_address(address).version == 6:
        cmd.extend(["-6", f"[{address}]:{ip_port}"])
    else:
        cmd.append(f"[{address}]:{ip_port}")

    env = os.environ.copy()

    env["OPENSSL_TIMEOUT"] = os.getenv("TIMEOUT", "30")
    env["CONNECT_TIMEOUT"] = env["OPENSSL_TIMEOUT"]
    output = subprocess.run(cmd, capture_output=True, env=env)
    output.check_returncode()

    return [({"openkat/testssl-sh-ciphers-output"}, Path("/tmp/output.json").read_bytes())]
