"""Boefje script for scanning wordpress sites using wpscan"""

import subprocess
from os import getenv

SCAN_TIMEOUT = 1800


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]
    info_mimetype = {"openkat/deschedule"}

    if input_["software"]["name"] != "WordPress":
        return [(info_mimetype, "Not wordpress.")]
    if "netloc" not in input_["ooi"] or "name" not in input_["ooi"]["netloc"]:
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

    # Can be overridden through the plugin settings, see schema.json.
    timeout = int(getenv("TIMEOUT", str(SCAN_TIMEOUT)))
    try:
        output = subprocess.run(["/usr/local/bin/wpscan"] + argv, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return [({"error/timeout"}, f"wpscan timed out for {url} after {timeout} seconds")]
    output.check_returncode()

    return [({"openkat/wp-scan"}, output.stdout.decode())]
