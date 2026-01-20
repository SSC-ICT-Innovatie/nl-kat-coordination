import os
import subprocess

REPO_INSTALLATION_PATH = "/data/repo"


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    # Creating the URL to check
    input_ooi = boefje_meta["arguments"]["input"]
    port = f":{input_ooi['port']}" if input_ooi["port"] else ""
    url = f"{input_ooi['scheme']}://{input_ooi['netloc']['name']}{port}{input_ooi['path']}"

    git_check_cmd = ["git", "ls-remote", url]

    # See if hostname is a git repository
    git_check_result = subprocess.run(git_check_cmd, capture_output=True, env={"GIT_TERMINAL_PROMPT": "0"})

    # Code 128 means that the repository does not exist or ls-remote has failed
    # In that case, we return an empty list
    if git_check_result.returncode == 128:
        return [({"openkat/octoscan-output"}, "[]")]
    git_check_result.check_returncode()

    org, repo = url.split("/")[-2:]
    download_cmd = [
        "/octoscan/octoscan",
        "dl",
        "--default-branch",
        "--output-dir",
        REPO_INSTALLATION_PATH,
        "--org",
        org,
        "--repo",
        repo,
        "--token",
        os.getenv("REPO_TOKEN", ""),
    ]

    # Download the repository's GitHub action workflows
    subprocess.run(download_cmd, capture_output=True).check_returncode()

    scan_cmd = ["/octoscan/octoscan", "scan", REPO_INSTALLATION_PATH, "--format", "json"]

    scan_output = subprocess.run(scan_cmd, capture_output=True)

    # Octoscan returns 0 when no problems are found, 1 when there is an error, and 2 when problems are found
    if scan_output.returncode == 1:
        raise Exception(
            f"Return code: {scan_output.returncode}; "
            f"Command: {scan_cmd}; "
            f"STDERR: {scan_output.stderr.decode()}; "
            f"STDIN: {scan_output.stdout.decode()}"
        )

    return [({"openkat/octoscan-output"}, scan_output.stdout.decode())]
