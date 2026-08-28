import docker

from boefjes.plugins.helpers import get_file_from_container

PLAYWRIGHT_IMAGE = "mcr.microsoft.com/playwright:latest"
BROWSER = "chromium"


class WebpageCaptureException(Exception):
    """Exception raised when webpage capture fails."""

    def __init__(self, message: str, container_log: str):
        self.message = message
        self.container_log = container_log

    def __str__(self) -> str:
        return str(self.message) + "\n\nContainer log:\n" + self.container_log


def build_playwright_command(webpage: str, browser: str, tmp_path: str) -> list[str]:
    """Returns playwright command including webpage, browser and locations for image, har and storage."""
    return [
        "/usr/bin/npx",
        "playwright",
        "screenshot",
        "-b",
        browser,
        "--full-page",
        "--ignore-https-errors",
        f"--save-har={tmp_path}.har.zip",
        f"--save-storage={tmp_path}.json",
        webpage,
        f"{tmp_path}.png",
    ]


def run_playwright(webpage: str, browser: str) -> tuple[bytes, bytes, bytes]:
    """Run Playwright in Docker."""
    tmp_path = "/tmp/output"  # noqa: S108
    client = docker.from_env()
    client.images.pull(PLAYWRIGHT_IMAGE)
    # https://playwright.dev/docs/docker#crawling-and-scraping
    command = build_playwright_command(webpage=webpage, browser=browser, tmp_path=tmp_path)
    container = client.containers.run(
        image=PLAYWRIGHT_IMAGE,
        command=command,
        detach=True,
        ipc_mode="host",
        user="pwuser",
        security_opt=[
            (
                'seccomp={"comment": "Allow create user namespaces", "names": ["clone", "setns", "unshare"], '
                '"action": "SCMP_ACT_ALLOW", "args": [], "includes": {}, "excludes": {}}'
            )
        ],
    )
    try:
        container.wait()
        image = get_file_from_container(container=container, path=f"{tmp_path}.png")
        har = get_file_from_container(container=container, path=f"{tmp_path}.har.zip")
        storage = get_file_from_container(container=container, path=f"{tmp_path}.json")
        if image is None or har is None or storage is None:
            raise WebpageCaptureException(
                "Playwright container did not return expected files, command was: " + " ".join(command),
                container.logs(stdout=True, stderr=True, timestamps=True).decode(),
            )

        return image, har, storage
    except docker.errors.NotFound:
        raise WebpageCaptureException(
            "Error while running Playwright container, command was: " + " ".join(command),
            container.logs(stdout=True, stderr=True, timestamps=True).decode(),
        )
    finally:
        container.remove()


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    """Creates webpage and takes capture using Playwright container."""
    input_ = boefje_meta["arguments"]["input"]
    webpage = f"{input_['scheme']}://{input_['netloc']['name']}{input_['path']}"

    image_png, har_zip, storage_json = run_playwright(webpage=webpage, browser=BROWSER)

    return [
        ({"image/png"}, image_png),
        ({"application/zip+json", "application/har+json"}, har_zip),
        ({"application/json", "application/localstorage+json"}, storage_json),
    ]
