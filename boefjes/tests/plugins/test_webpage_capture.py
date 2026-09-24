import subprocess

import pytest

from boefjes.plugins.kat_webpage_capture.main import (
    WebpageCaptureException,
    build_playwright_command,
    playwright_log,
    run_playwright,
)


def test_command_calls_pinned_binary_not_npx(tmp_path):
    # Regression for #3916: `npx playwright` fetches the latest Playwright at
    # runtime, which breaks against the browser baked into the image. The command
    # must invoke the pinned, installed binary directly.
    command = build_playwright_command("https://example.com/", "chromium", str(tmp_path / "output"))

    assert command[0] == "playwright"
    assert not any("npx" in part for part in command)


def test_command_captures_har_screenshot_and_storage(tmp_path):
    base = str(tmp_path / "output")
    command = build_playwright_command("https://example.com/", "chromium", base)

    assert command[:3] == ["playwright", "screenshot", "-b"]
    assert f"--save-har={base}.har.zip" in command
    assert f"--save-storage={base}.json" in command
    assert command[-2:] == ["https://example.com/", f"{base}.png"]


# The real stderr of the failure reported from a production stack: an image predating #5333
# still ran `npx playwright`, which fetched a newer Playwright than the baked browser (#3916).
# Reproduced in mcr.microsoft.com/playwright:v1.53.0-noble -- stdout was empty, all 1177 bytes
# of the explanation went to stderr.
PLAYWRIGHT_FAILURE_STDERR = (
    b"npm warn exec The following package was not found and will be installed: playwright@1.63.0\n"
    b"Error: command.parse: Executable doesn't exist at "
    b"/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-linux-arm64/chrome-headless-shell\n"
    b"Looks like Playwright was just updated to 1.63.0.\n"
    b"Please update docker image as well.\n"
)


def _failed_run(returncode=1, stdout=b"", stderr=PLAYWRIGHT_FAILURE_STDERR):
    return subprocess.CompletedProcess(args=["playwright"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_nonzero_exit_reports_why_playwright_failed(monkeypatch):
    # Regression: run_playwright used subprocess.check_returncode(), whose CalledProcessError
    # renders neither stream. A failing capture produced a traceback with no diagnosis at all.
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _failed_run())

    with pytest.raises(WebpageCaptureException) as excinfo:
        run_playwright(webpage="https://example.com/", browser="chromium")

    message = str(excinfo.value)
    assert "Executable doesn't exist" in message
    assert "Please update docker image as well." in message
    assert "exited with code 1" in message


def test_missing_files_report_stderr_not_just_stdout(monkeypatch, tmp_path):
    # The container log was built from output.stdout alone, which Playwright leaves empty on
    # failure -- so this path logged nothing exactly when it had something to say.
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _failed_run(returncode=0))

    with pytest.raises(WebpageCaptureException) as excinfo:
        run_playwright(webpage="https://example.com/", browser="chromium")

    assert "Executable doesn't exist" in str(excinfo.value)


def test_log_labels_both_streams_and_skips_empty_ones():
    both = playwright_log(_failed_run(stdout=b"navigating\n"))
    assert "stdout:\nnavigating" in both
    assert "stderr:\nnpm warn exec" in both

    # An empty stream is omitted rather than printed as an empty labelled section.
    assert "stdout:" not in playwright_log(_failed_run(stdout=b""))


def test_log_survives_undecodable_output():
    assert playwright_log(_failed_run(stderr=b"\xff\xfe broken")) is not None
