import re
import subprocess


def run_drill(domain: str, record_type: str) -> bytes:
    cmd = ["/usr/bin/drill", "-DT", domain, record_type]

    output = subprocess.run(cmd, capture_output=True)
    output.check_returncode()

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
