import logging
import os
import subprocess
from pathlib import Path


def run_masscan(target_ip: str):
    # Scan according to arguments.
    port_range = os.getenv("PORTS", "53,80,443")
    max_rate = os.getenv("MAX_RATE", "100")
    logging.info("Running masscan...")
    cmd = [
        "/app/boefje/masscan/bin/masscan",
        "-p",
        port_range,
        "--max-rate",
        max_rate,
        "-oJ",
        "/tmp/out.json",
        target_ip,
    ]
    output = subprocess.run(cmd, capture_output=True)
    output.check_returncode()


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    """Creates webpage and takes capture using Playwright container."""
    input_ = boefje_meta["arguments"]["input"]
    ip_range = f"{input_['start_ip']['address']}/{str(input_['mask'])}"
    run_masscan(target_ip=ip_range)
    m_run = Path("/tmp/out.json").read_bytes()
    logging.info("Received a response with length %d", len(m_run))

    return [({"openkat/masscan-output"}, m_run)]
