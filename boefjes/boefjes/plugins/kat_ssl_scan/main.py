import subprocess

BOEFJE_TIMEOUT_SECONDS = 120

# Services sslscan can probe: directly TLS-capable, STARTTLS-capable, and
# RDP (probed with the RDP preamble).
TLS_CAPABLE_SERVICES = ("https", "ftps", "smtps", "imaps", "pop3s")
STARTTLS_CAPABLE_SERVICES = ("pop3", "ftp", "imap", "smtp", "mysql", "ldap", "xmpp")
RDP_SERVICES = ("ms-wbt-server",)


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]

    if input_["object_type"] == "IPService":
        # A connection without a server name: no --sni-name is passed. Note
        # that sslscan then defaults the SNI name to the host it was given
        # (the IP literal) — its own documented behavior, not a true null
        # SNI handshake.
        ip = input_["ip_port"]["address"]["address"]
        port = input_["ip_port"]["port"]
        servicename = input_["service"]["name"]
        hostname = None
    else:
        # HostnameIPService: connect for that server name. The argument is
        # one entry, "--sni-name=<name>": sslscan parses the value from the
        # same argv entry (strncmp + offset), so a separate argv element
        # leaves the SNI name empty and silently unscanned.
        hostname = input_["hostname"]["name"]
        ip = input_["ip_service"]["ip_port"]["address"]["address"]
        port = input_["ip_service"]["ip_port"]["port"]
        servicename = input_["ip_service"]["service"]["name"]

    if servicename not in TLS_CAPABLE_SERVICES + STARTTLS_CAPABLE_SERVICES + RDP_SERVICES:
        return [({"openkat/deschedule"}, f"Skipping check due to non-TLS/STARTTLS service: {servicename}")]

    command = ["/usr/bin/sslscan", "--no-colour", "--show-sigs"]
    if servicename in STARTTLS_CAPABLE_SERVICES:
        command.append(f"--starttls-{servicename}")
    elif servicename in RDP_SERVICES:
        command.append("--rdp")

    if hostname:
        command.append(f"--sni-name={hostname}")

    # sslscan parses bracketed IPv6 targets itself (strips the brackets).
    target = f"[{ip}]:{port}"

    command.extend(["--xml=-", target])
    try:
        output = subprocess.run(command, capture_output=True, timeout=BOEFJE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as e:
        partial = (e.stdout or b"").decode(errors="replace")
        message = f"sslscan of [{ip}]:{port} timed out after {BOEFJE_TIMEOUT_SECONDS}s"
        return [({"error/timeout"}, f"{message}\n{partial}".strip())]

    # sslscan writes an XML document even when the connection fails: the
    # <ssltest> element (with the <protocol> entries) only appears when the
    # connection was established. Header plus <error> elements without
    # <ssltest> means the connection itself failed; the reason travels in
    # the raw bytes, no normalizer consumes it.
    if b"<ssltest" not in output.stdout:
        combined = (output.stderr or b"") + (output.stdout or b"")
        return [({"error/boefje"}, combined.decode(errors="replace").strip())]

    # sslscan exits 0 even for unreachable hosts, so the exit code carries
    # no signal; the XML is the result.
    return [({"openkat/ssl-scan-output"}, output.stdout.decode())]
