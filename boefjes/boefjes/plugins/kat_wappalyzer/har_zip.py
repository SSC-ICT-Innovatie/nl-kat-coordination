"""Read a Playwright browser HAR for the Wappalyzer analysis.

`kat_webpage_capture` runs `playwright screenshot --save-har=<file>.zip`, which
writes a ZIP archive: the HAR document lives in `har.har`, and every response
body is stored as a separate file referenced by `content._file` rather than
inline `content.text`. tanimachi's `Har.model_validate_json` reads
`content.text`, so the bodies have to be inlined before analysis.
"""

import contextlib
import io
import json
import zipfile


def har_from_playwright_zip(raw: bytes) -> bytes:
    """Return a HAR JSON (bytes) with response bodies inlined into content.text.

    Accepts either a Playwright `.zip` HAR archive or a plain (already inline)
    HAR document, so callers do not have to know which shape they were given.
    """
    if not zipfile.is_zipfile(io.BytesIO(raw)):
        return raw

    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        # A zip that is not a Playwright HAR archive (no `har.har` member) is
        # neither shape we handle; pass it through instead of raising KeyError.
        if "har.har" not in archive.namelist():
            return raw

        har = json.loads(archive.read("har.har"))

        for entry in har.get("log", {}).get("entries", []):
            content = entry.get("response", {}).get("content", {})
            file_name = content.pop("_file", None)

            if not file_name or content.get("text"):
                continue

            # A referenced body missing from the archive should not abort the
            # whole analysis; the entry is simply left without a body.
            with contextlib.suppress(KeyError):
                content["text"] = _decode_body(archive.read(file_name))

    return json.dumps(har).encode()


def _decode_body(body: bytes) -> str:
    """Decode a response body without losing bytes on non-UTF-8 pages.

    Wappalyzer matches (mostly ASCII) regexes over the body, so dropping bytes
    with errors="ignore" could hide a detection on a latin-1/utf-16 page. Fall
    back to latin-1, which never raises and maps every byte 1:1.
    """
    try:
        return body.decode()
    except UnicodeDecodeError:
        return body.decode("latin-1")
