import re
import subprocess

# ldns exit code for LDNS_STATUS_NETWORK_ERR ("Could not send or receive, because of network error").
# drill -T queries the root and authoritative nameservers directly, so this is what drill exits with
# when those direct queries go unanswered, whatever the cause (connectivity, routing, egress filtering).
LDNS_NETWORK_ERR = 20
DRILL_TIMEOUT_SECONDS = 30


def run_drill(domain: str, record_type: str) -> bytes:
    cmd = ["/usr/bin/drill", "-DT", domain, record_type]

    try:
        output = subprocess.run(cmd, capture_output=True, timeout=DRILL_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"drill timed out for {domain} ({record_type})") from exc
    if output.returncode != 0:
        stderr = output.stderr.decode(errors="replace").strip()
        message = f"drill exited with status {output.returncode} for {domain} ({record_type})"
        if stderr:
            message += f": {stderr}"
        if output.returncode == LDNS_NETWORK_ERR:
            message += (
                ". DNSSEC tracing (drill -T) queries the root and authoritative nameservers directly and "
                "got no answer. This points at a connectivity problem rather than the domain's DNSSEC state: "
                "for example local network loss, a routing problem towards the nameservers, or an egress "
                "policy that only allows DNS through a local resolver."
            )
        raise RuntimeError(message)

    return output.stdout


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]
    domain = input_["name"]

    domain = normalize_hostname(domain)

    output = run_drill(domain, "A")
    if is_no_data(output, domain, "A"):
        output = run_drill(domain, "CNAME")
        if is_no_data(output, domain, "CNAME"):
            output = run_drill(domain, "AAAA")

    return [({"openkat/dnssec-output"}, output)]


def normalize_hostname(value: str) -> str:
    """Validate a DNS hostname and return its lower-case ASCII/IDNA form."""
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("Invalid hostname")
    value = value.rstrip(".")
    try:
        labels = [label.encode("idna").decode("ascii").lower() for label in value.split(".")]
    except UnicodeError as exc:
        raise ValueError("Invalid IDNA hostname") from exc
    if (
        not labels
        or len(".".join(labels)) > 253
        or any(
            not 1 <= len(label) <= 63 or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label) for label in labels
        )
    ):
        raise ValueError("Invalid DNS hostname")
    return ".".join(labels)


def is_no_data(output: bytes, domain: str, record_type: str) -> bool:
    """Match explicit no-data output regardless of DNSSEC status marker."""
    return any(
        re.fullmatch(
            rf"\[[USTB]\] No data found for: {re.escape(domain)}\.? type {record_type}", line.strip(), re.IGNORECASE
        )
        for line in output.decode("utf-8", errors="replace").splitlines()
    )
