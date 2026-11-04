import gzip
import io
import tarfile
import zipfile

from boefjes.plugins.kat_archive_unpacker import normalize
from boefjes.plugins.kat_archive_unpacker.normalize import run
from boefjes.plugins.unpack_common import UnpackGuard


def _zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buf.getvalue()


def test_zip_unpacker_extracts_members():
    raw = _zip({"index.html": b"<html>", "app.js": b"x=1", "sub/dir/": b""})  # dir entry ignored

    results = list(run({}, raw))

    contents = {r.content for r in results}
    assert contents == {b"<html>", b"x=1"}
    html = next(r for r in results if r.content == b"<html>")
    assert "text/html" in html.mime_types
    assert any(t.startswith("archive-member/") for t in html.mime_types)


def test_tar_unpacker_extracts_files_only():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        data = b"body{color:red}"
        info = tarfile.TarInfo("style.css")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))

    results = list(run({}, buf.getvalue()))

    assert len(results) == 1
    assert results[0].content == b"body{color:red}"
    assert "text/css" in results[0].mime_types


def test_gzip_single_stream():
    results = list(run({}, gzip.compress(b"hello world")))

    assert len(results) == 1
    assert results[0].content == b"hello world"


def test_nested_archive_is_neutralised_not_reexploded():
    inner = _zip({"secret.txt": b"deep"})
    raw = _zip({"nested.zip": inner})

    results = list(run({}, raw))

    assert len(results) == 1
    member = results[0]
    assert member.content == inner
    # Must NOT carry an archive mime type: that would re-trigger this unpacker (bomb amplification).
    assert "application/zip" not in member.mime_types
    assert "application/octet-stream" in member.mime_types
    assert any(t.startswith("nested-archive/") for t in member.mime_types)


def test_archive_unpacker_respects_guard(monkeypatch):
    raw = _zip({f"f{i}.txt": f"data{i}".encode() for i in range(5)})
    monkeypatch.setattr(normalize, "UnpackGuard", lambda: UnpackGuard(max_files=2))

    assert len(list(run({}, raw))) == 2


def test_path_traversal_name_reduced_to_basename():
    # We never write members to disk, but a traversal-style name must not leak into the mime guess.
    raw = _zip({"../../etc/passwd": b"root:x:0:0:"})

    results = list(run({}, raw))

    assert len(results) == 1
    assert results[0].content == b"root:x:0:0:"
