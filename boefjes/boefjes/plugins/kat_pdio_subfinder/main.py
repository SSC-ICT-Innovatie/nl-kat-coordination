import logging
import os
import subprocess

HARD_TIMEOUT = 600


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    """Run subfinder with only active domains output."""
    rate_limit = int(os.getenv("SUBFINDER_RATE_LIMIT", "2"))
    timeout = int(os.getenv("SUBFINDER_RATE_TIMEOUT", "30"))
    # Can be overridden through the plugin settings, see schema.json. A hard
    # wall-clock budget; the per-host -timeout alone does not bound the run.
    hard_timeout = int(os.getenv("TIMEOUT", str(HARD_TIMEOUT)))
    input_ = boefje_meta["arguments"]["input"]
    hostname = input_["hostname"]["name"]

    logging.info("Using subfinder with rate limit %s on %s", rate_limit, hostname)

    try:
        output = subprocess.run(
            [
                "/usr/local/bin/subfinder",
                "-silent",
                "-active",
                "-rate-limit",
                str(rate_limit),
                "-d",
                hostname,
                "-all",
                "-timeout",
                str(timeout),
            ],
            capture_output=True,
            timeout=hard_timeout,
        )
    except subprocess.TimeoutExpired:
        return [({"error/timeout"}, f"subfinder timed out for {hostname} after {hard_timeout} seconds")]
    output.check_returncode()

    return [({"openkat/pdio-subfinder"}, output.stdout.decode())]
