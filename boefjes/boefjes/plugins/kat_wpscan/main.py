"""Boefje script for scanning wordpress sites using wpscan"""

from os import getenv

import docker

WPSCAN_IMAGE = "wpscanteam/wpscan:latest"


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]
    info_mimetype = {"info/boefje"}

    if input_["software"]["name"] != "WordPress":
        return [(info_mimetype, "Not wordpress.")]
    if "netloc" not in input_["ooi"] or "name" not in input_["ooi"]["netloc"].dict():
        return [(info_mimetype, "No hostname available for input OOI.")]

    hostname = input_["ooi"]["netloc"]["name"]
    path = input_["ooi"]["path"]
    scheme = input_["ooi"]["scheme"]

    if scheme != "https":
        return [(info_mimetype, "To avoid double findings, we only scan https urls.")]

    url = f"{scheme}://{hostname}{path}"

    argv = ["--url", url, "--format", "json", "--plugins-version-detection", "aggressive"]
    if wpscan_api_token := getenv("WP_SCAN_API"):
        argv += ["--api-token", wpscan_api_token]

    # update WPScan image
    client = docker.from_env()
    client.images.pull(WPSCAN_IMAGE)

    # since WPScan can give positive exit codes on completion, docker-py's run() can fail on this
    container = client.containers.run(WPSCAN_IMAGE, argv, detach=True)

    try:
        # wait for container to exit, read its output in the logs and remove container
        container.wait()
        output = container.logs()
    finally:
        container.remove()

    return [(set(), output)]
