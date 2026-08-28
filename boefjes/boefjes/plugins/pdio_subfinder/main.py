import logging
import os

import docker


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    """Create image from docker and run subfinder with only active domains output."""
    subfinder_image = f"projectdiscovery/subfinder:{os.getenv('SUBFINDER_VERSION', 'v2.6.6')}"
    rate_limit = int(os.getenv("SUBFINDER_RATE_LIMIT", "0"))

    client = docker.from_env()
    input_ = boefje_meta["arguments"]["input"]
    hostname = input_["name"]

    logging.info("Using %s with rate limit %s", subfinder_image, rate_limit)
    output = client.containers.run(
        subfinder_image, ["-silent", "-active", "-rate-limit", str(rate_limit), "-d", hostname], remove=True
    )

    return [(set(), output)]
