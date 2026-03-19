import subprocess


def verify_hostname_meta(input_ooi):
    return input_ooi["name"]


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    # Checks if the url is of object HostnameHTTPURL or Hostname
    url = verify_hostname_meta(boefje_meta["arguments"]["input"])
    cmd = ["/usr/local/bin/nuclei"] + boefje_meta["arguments"]["oci_arguments"] + ["-u", url]

    output = subprocess.run(cmd, capture_output=True)
    output.check_returncode()

    return [({"openkat/nuclei-output"}, output.stdout.decode())]
