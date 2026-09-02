import re
import subprocess

# ldns exit code for LDNS_STATUS_NETWORK_ERR ("Could not send or receive, because of network error").
# drill -T queries the root and authoritative nameservers directly, so this is what drill exits with
# when the scanner's network only allows DNS through a local resolver.
LDNS_NETWORK_ERR = 20


def run_drill(domain: str, record_type: str) -> bytes:
    cmd = ["/usr/bin/drill", "-DT", domain, record_type]

    output = subprocess.run(cmd, capture_output=True)
    if output.returncode != 0:
        stderr = output.stderr.decode(errors="replace").strip()
        message = f"drill exited with status {output.returncode} for {domain} ({record_type})"
        if stderr:
            message += f": {stderr}"
        if output.returncode == LDNS_NETWORK_ERR:
            message += (
                ". DNSSEC tracing (drill -T) queries the root and authoritative nameservers directly, "
                "so outbound UDP and TCP port 53 to arbitrary hosts must be allowed; "
                "a resolver-only egress policy is not enough."
            )
        raise RuntimeError(message)

    return output.stdout


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]
    domain = input_["name"]

    # check for string pollution in domain. This check will fail if anything other characters than a-zA-Z0-9_.- are
    # present in the hostname
    if not re.search(r"^[\w.]+[\w\-.]+$", domain.lower()):
        raise ValueError(
            "This domain contains prohibited characters. Are you sure you are not trying to add a url instead of a "
            "hostname?"
        )

    output = run_drill(domain, "A")
    if f"[U] No data found for: {domain}. type A".encode() in output:
        output = run_drill(domain, "CNAME")
        if f"[U] No data found for: {domain}. type CNAME".encode() in output:
            output = run_drill(domain, "AAAA")

    return [({"openkat/dnssec-output"}, output)]
