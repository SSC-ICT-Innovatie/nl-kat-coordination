import subprocess
from os import getenv

SCAN_TIMEOUT = 300


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ooi = boefje_meta["arguments"]["input"]
    api_url = input_ooi["api_url"]

    hostname = api_url["netloc"]["name"]
    path = api_url["path"]
    scheme = api_url["scheme"]

    url = f"{scheme}://{hostname}{path}"
    cmd = ["/usr/local/bin/adr-validator", "-format", "json", url]

    # Can be overridden through the plugin settings, see schema.json.
    timeout = int(getenv("TIMEOUT", str(SCAN_TIMEOUT)))
    try:
        output = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return [({"error/timeout"}, f"adr-validator timed out for {url} after {timeout} seconds")]
    output.check_returncode()

    return [({"openkat/adr-validator-output"}, output.stdout.decode())]
