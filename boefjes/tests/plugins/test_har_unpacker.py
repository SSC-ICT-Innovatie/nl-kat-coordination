import base64
import datetime
import json
from datetime import timezone
from uuid import UUID

from boefjes.plugins.kat_har_unpacker import normalize
from boefjes.plugins.kat_har_unpacker.normalize import run
from boefjes.plugins.unpack_common import UnpackGuard
from boefjes.worker.job_models import Boefje, BoefjeMeta, Normalizer, NormalizerMeta, RawDataMeta


def _entry(url: str, mime: str, text: str, encoding: str | None = None) -> dict:
    content: dict = {"size": len(text), "mimeType": mime, "text": text}
    if encoding:
        content["encoding"] = encoding
    return {
        "startedDateTime": "2024-01-01T00:00:00+00:00",
        "time": 0,
        "request": {
            "method": "GET",
            "url": url,
            "httpVersion": "HTTP/1.1",
            "cookies": [],
            "headers": [],
            "queryString": [],
            "headersSize": -1,
            "bodySize": -1,
        },
        "response": {
            "status": 200,
            "statusText": "OK",
            "httpVersion": "HTTP/1.1",
            "cookies": [],
            "headers": [],
            "content": content,
            "redirectURL": "",
            "headersSize": -1,
            "bodySize": 0,
        },
        "cache": {},
        "timings": {"send": 0, "wait": 0, "receive": 0},
    }


def _har(entries: list[dict]) -> bytes:
    return json.dumps(
        {"log": {"version": "1.2", "creator": {"name": "t", "version": "1"}, "entries": entries}}
    ).encode()


def test_har_unpacker_extracts_bodies_with_mime_types():
    raw = _har(
        [
            _entry("https://example.com/", "text/html; charset=utf-8", "<html>hi</html>"),
            _entry("https://example.com/app.js", "application/javascript", "console.log(1)"),
        ]
    )

    results = list(run({}, raw))

    assert len(results) == 2
    html = next(r for r in results if r.content == b"<html>hi</html>")
    assert "text/html" in html.mime_types  # charset stripped
    assert any(t.startswith("har-resource/") for t in html.mime_types)  # discriminator present
    js = next(r for r in results if r.content == b"console.log(1)")
    assert "application/javascript" in js.mime_types


def test_har_unpacker_decodes_base64_bodies():
    payload = b"\x89PNG\r\n\x1a\n binary"
    raw = _har([_entry("https://example.com/x.png", "image/png", base64.b64encode(payload).decode(), "base64")])

    results = list(run({}, raw))

    assert len(results) == 1
    assert results[0].content == payload
    assert "image/png" in results[0].mime_types


def test_har_unpacker_skips_empty_bodies():
    raw = _har([_entry("https://example.com/", "text/html", "")])

    assert list(run({}, raw)) == []


def test_har_unpacker_respects_guard(monkeypatch):
    raw = _har([_entry(f"https://example.com/{i}", "text/html", f"body{i}") for i in range(5)])
    monkeypatch.setattr(normalize, "UnpackGuard", lambda: UnpackGuard(max_files=2))

    assert len(list(run({}, raw))) == 2


def _har_normalizer_meta() -> NormalizerMeta:
    boefje_meta = BoefjeMeta(
        id=UUID("d63d755b-6c23-44ab-8de6-8d144c448a71"),
        boefje=Boefje(id="kat_webpage_analysis"),
        input_ooi="Hostname|internet|test.org",
        arguments={},
        organization="test",
        started_at=datetime.datetime(1000, 10, 10, 10, 10, 10, tzinfo=timezone.utc),
        ended_at=datetime.datetime(1000, 10, 10, 10, 10, 11, tzinfo=timezone.utc),
    )
    return NormalizerMeta(
        id=UUID("203eedee-a590-43e1-8f80-6d18ffe529f5"),
        raw_data=RawDataMeta(
            id=UUID("2c9f47db-dfca-4928-b29f-368e64b3c779"),
            boefje_meta=boefje_meta,
            mime_types=[{"value": "application/json+har"}],
        ),
        normalizer=Normalizer(id="kat_har_unpacker"),
        started_at=datetime.datetime(1001, 10, 10, 10, 10, 10, tzinfo=timezone.utc),
        ended_at=datetime.datetime(1001, 10, 10, 10, 10, 12, tzinfo=timezone.utc),
    )


def test_runner_collects_raw_files_and_no_observations(normalizer_runner):
    # End-to-end through the real runner + real plugin: verifies runner._parse_results routes
    # NormalizerRawFile output into NormalizerResults.raw_files and yields no OOI observations.
    raw = _har([_entry("https://example.com/", "text/html", "<html>hi</html>")])

    results = normalizer_runner.run(_har_normalizer_meta(), raw)

    assert results.raw_files
    assert not results.observations
    assert any("text/html" in rf.mime_types for rf in results.raw_files)
