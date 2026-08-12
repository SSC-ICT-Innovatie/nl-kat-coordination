import subprocess
from pathlib import Path

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
    command = build_playwright_command(webpage=webpage, browser=browser, tmp_path=tmp_path)
    output = subprocess.run(command, capture_output=True)
    output.check_returncode()

    try:
        image = Path(f"{tmp_path}.png").read_bytes()
        har = Path(f"{tmp_path}.har.zip").read_bytes()
        storage = Path(f"{tmp_path}.json").read_bytes()
    except FileNotFoundError:
        raise WebpageCaptureException(
            "Playwright container did not return expected files, command was: " + " ".join(command),
            output.stdout.decode(),
        )

    return image, har, storage


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
