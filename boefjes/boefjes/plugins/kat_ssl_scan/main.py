import subprocess

TLS_CAPABLE_SERVICES = ("https", "ftps", "smtp", "smtps", "imaps", "pop3s", "ms-wbt-server")
STARTTLS_CAPABLE_SERVICES = ("pop3", "ftp", "imap", "smtp", "mysql", "ldap", "xmpp")


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]
    hostname = None
    if "hostname" in input_:
        # we are dealing with a website
        hostname = input_["hostname"]["name"]
        ip = input_["ip_service"]["ip_port"]["address"]["address"]
        port = input_["ip_service"]["ip_port"]["port"]
        servicename = input_["ip_service"]["service"]["name"]
    else:
        # we are dealing with an IP-service
        ip = input_["ip_port"]["address"]["address"]
        port = input_["ip_port"]["port"]
        servicename = input_["service"]["name"]

    if servicename not in TLS_CAPABLE_SERVICES + STARTTLS_CAPABLE_SERVICES:
        return [({"info/boefje"}, "Skipping check due to non-TLS/STARTTLS service")]

    command = ["/usr/bin/sslscan", "--no-colour", "--show-sigs"]
    if servicename in STARTTLS_CAPABLE_SERVICES:
        command.append(f"--starttls-{servicename}")
    elif servicename == "ms-wbt-server":
        command.append("--rdp")

    if hostname:
        command.extend(["--sni-name=", hostname])

    target = f"[{ip}]:{port}"

    command.extend(["--xml=-", target])
    output = subprocess.run(command, capture_output=True)
    output.check_returncode()

    return [({"openkat/ssl-scan-output"}, output.stdout.decode())]
