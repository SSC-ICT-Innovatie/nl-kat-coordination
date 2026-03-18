import subprocess


def get_target_url(input_ooi: dict) -> str:
    """Extract scan target from Hostname or HostnameHTTPURL input."""
    if input_ooi.get("object_type") == "HostnameHTTPURL":
        scheme = input_ooi["scheme"]
        hostname = input_ooi["netloc"].split("|")[-1]
        port = input_ooi["port"]
        path = input_ooi["path"]
        return f"{scheme}://{hostname}:{port}{path}"
    return input_ooi["name"]


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    url = get_target_url(boefje_meta["arguments"]["input"])
    cmd = ["/usr/local/bin/nuclei"] + boefje_meta["arguments"]["oci_arguments"] + ["-u", url]

    output = subprocess.run(cmd, capture_output=True)
    output.check_returncode()

    return [({"openkat/nuclei-output"}, output.stdout.decode())]
