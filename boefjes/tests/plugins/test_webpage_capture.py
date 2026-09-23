from boefjes.plugins.kat_webpage_capture.main import build_playwright_command


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
