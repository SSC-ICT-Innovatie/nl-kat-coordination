import logging
import os

import docker

from boefjes.plugins.helpers import get_file_from_container

IMAGE = "ghcr.io/minvws/nl-kat-masscan-build-image:latest"
FILE_PATH = "/tmp/output.json"  # noqa: S108


def run_masscan(target_ip: str) -> bytes:
    """Run Masscan in Docker."""
    client = docker.from_env()

    # Scan according to arguments.
    port_range = os.getenv("PORTS", "53,80,443")
    max_rate = os.getenv("MAX_RATE", 100)
    logging.info("Starting container %s to run masscan...", IMAGE)
    res = client.containers.run(
        image=IMAGE, command=f"-p {port_range} --max-rate {max_rate} -oJ {FILE_PATH} {target_ip}", detach=True
    )
    res.wait()
    logging.debug(res.logs())

    output = get_file_from_container(container=res, path=FILE_PATH)

    if not output:
        raise Exception(f"Couldn't get {FILE_PATH} from masscan container")

    # Do not crash the boefje if the output is known, instead log a warning.
    try:
        res.remove()
    except Exception as e:
        logging.warning(e)

    return output


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    """Creates webpage and takes capture using Playwright container."""
    input_ = boefje_meta["arguments"]["input"]
    ip_range = f"{input_['start_ip']['address']}/{str(input_['mask'])}"
    m_run = run_masscan(target_ip=ip_range)
    logging.info("Received a response with length %d", len(m_run))

    return [(set(), m_run)]
