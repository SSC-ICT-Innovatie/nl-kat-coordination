import subprocess


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ooi = boefje_meta["arguments"]["input"]
    api_url = input_ooi["api_url"]

    hostname = api_url["netloc"]["name"]
    path = api_url["path"]
    scheme = api_url["scheme"]

    url = f"{scheme}://{hostname}{path}"
    cmd = ["/usr/local/bin/adr-validator", "-format", "json", url]

    output = subprocess.run(cmd, capture_output=True)
    output.check_returncode()

    return [({"openkat/adr-validator-output"}, output.stdout.decode())]
