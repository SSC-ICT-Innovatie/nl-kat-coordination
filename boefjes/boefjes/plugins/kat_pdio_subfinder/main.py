import logging
import os
import subprocess


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    """Run subfinder with only active domains output."""
    rate_limit = int(os.getenv("SUBFINDER_RATE_LIMIT", "0"))
    input_ = boefje_meta["arguments"]["input"]
    hostname = input_["name"]

    logging.info("Using subfinder with rate limit %s on %s", rate_limit, hostname)

    output = subprocess.run(
        ["/usr/local/bin/subfinder", "-silent", "-active", "-rate-limit", str(rate_limit), "-d", hostname],
        capture_output=True,
    )
    output.check_returncode()

    return [({"openkat/pdio-subfinder"}, output.stdout.decode())]
