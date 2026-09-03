import io
import json
import zipfile

from boefjes.plugins.kat_wappalyzer.har_zip import har_from_playwright_zip


def _playwright_har_zip(bodies: dict[str, str], entries: list[dict], *, extra_files: dict[str, str] | None = None):
    """Build a Playwright-shaped HAR zip: `har.har` plus body files by `_file`."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("har.har", json.dumps({"log": {"entries": entries}}))
        for name, content in {**bodies, **(extra_files or {})}.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _entry(file_name: str, mime: str = "text/html"):
    return {"response": {"content": {"mimeType": mime, "_file": file_name}}}


def test_inlines_file_bodies_into_content_text():
    raw = _playwright_har_zip(
        bodies={"a.html": "<html>wp-content</html>", "b.css": "body{}"},
        entries=[_entry("a.html"), _entry("b.css", "text/css")],
    )

    har = json.loads(har_from_playwright_zip(raw))
    first, second = (e["response"]["content"] for e in har["log"]["entries"])

    assert first["text"] == "<html>wp-content</html>"
    assert "_file" not in first
    assert second["text"] == "body{}"


def test_missing_body_file_does_not_abort():
    raw = _playwright_har_zip(bodies={}, entries=[_entry("gone.html")])

    har = json.loads(har_from_playwright_zip(raw))
    content = har["log"]["entries"][0]["response"]["content"]

    assert "_file" not in content
    assert "text" not in content


def test_plain_har_is_passed_through_unchanged():
    plain = json.dumps({"log": {"entries": []}}).encode()

    assert har_from_playwright_zip(plain) == plain
