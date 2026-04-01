import subprocess


def get_target_url(input_ooi: dict) -> str:
    """Extract scan target hostname from input OOI."""
    return input_ooi["name"]


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    url = get_target_url(boefje_meta["arguments"]["input"])
    cmd = ["/usr/local/bin/nuclei"] + boefje_meta["arguments"]["oci_arguments"] + ["-u", url]

    output = subprocess.run(cmd, capture_output=True)
    output.check_returncode()

    return [({"openkat/nuclei-output"}, output.stdout.decode())]
