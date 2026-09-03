import gzip
import io
import mimetypes
import tarfile
import zipfile
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput, NormalizerRawFile
from boefjes.plugins.unpack_common import MAX_FILE_BYTES, UnpackGuard, discriminator_tag, normalize_mime_type


def run(input_ooi: dict, raw: bytes | str) -> Iterable[NormalizerOutput]:
    """Unpack a zip/tar/gzip archive into one raw file per member.

    Members are read into memory (never extracted to disk) with strict decompression-bomb limits.
    A member that is itself an archive is re-emitted with its archive mime type and re-dispatched to
    this unpacker by the scheduler; nesting is bounded by the per-run size and count limits.
    """
    data = raw if isinstance(raw, bytes) else raw.encode()
    guard = UnpackGuard()

    if zipfile.is_zipfile(io.BytesIO(data)):
        yield from _iter_zip(data, guard)
        return

    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
            yield from _iter_tar(tar, guard)
        return
    except tarfile.TarError:
        pass

    yield from _iter_gzip(data, guard)


def _raw_file(name: str, content: bytes) -> NormalizerRawFile:
    if _looks_like_archive(content):
        # Do not re-emit a nested archive under an archive mime type: that would re-trigger this
        # unpacker and let a nested bomb (e.g. 42.zip) amplify across scheduler tasks and Bytes
        # storage, even though every individual member is size-bounded. Surface it as an opaque blob
        # instead. Recursively unpacking nested archives (with a real depth cap) is a deliberate
        # follow-up, which needs the raw's own mime types passed into the normalizer.
        mime, prefix = "application/octet-stream", "nested-archive"
    else:
        guessed, _ = mimetypes.guess_type(_safe_name(name))
        mime, prefix = normalize_mime_type(guessed), "archive-member"

    return NormalizerRawFile(content=content, mime_types={mime, discriminator_tag(prefix, content)})


def _looks_like_archive(content: bytes) -> bool:
    """Magic-byte sniff for the archive formats this unpacker consumes, so a nested archive is not
    re-dispatched to itself (bomb-amplification guard). Independent of the (attacker-controlled) name."""
    if content[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):  # zip
        return True
    if content[:2] == b"\x1f\x8b":  # gzip
        return True
    if content[:3] == b"BZh":  # bzip2 (tar.bz2)
        return True
    if content[:6] == b"\xfd7zXZ\x00":  # xz (tar.xz)
        return True
    if len(content) > 262 and content[257:262] == b"ustar":  # tar
        return True
    return False


def _safe_name(name: str) -> str:
    """Reduce an archive member name to its bare basename. We never write members to disk, but this
    keeps a traversal-style name (``../../etc/passwd``) from leaking into the mime-type guess or logs."""
    return name.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]


def _iter_zip(data: bytes, guard: UnpackGuard) -> Iterable[NormalizerOutput]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for info in archive.infolist():
            if guard.exhausted():
                break
            if info.is_dir():
                continue
            if guard.file_too_large(info.file_size):  # uncompressed size from the header: cheap bomb check
                continue
            try:
                content = archive.read(info)
            except (RuntimeError, zipfile.BadZipFile, OSError):
                continue  # encrypted or corrupt member
            if not content or guard.file_too_large(len(content)):
                continue
            guard.register(len(content))
            yield _raw_file(info.filename, content)


def _iter_tar(tar: tarfile.TarFile, guard: UnpackGuard) -> Iterable[NormalizerOutput]:
    for member in tar:
        if guard.exhausted():
            break
        if not member.isfile():
            continue
        if guard.file_too_large(member.size):
            continue
        extracted = tar.extractfile(member)
        if extracted is None:
            continue
        content = extracted.read(MAX_FILE_BYTES + 1)
        if not content or guard.file_too_large(len(content)):
            continue
        guard.register(len(content))
        yield _raw_file(member.name, content)


def _iter_gzip(data: bytes, guard: UnpackGuard) -> Iterable[NormalizerOutput]:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            content = stream.read(MAX_FILE_BYTES + 1)  # bounded read guards against a gzip bomb
    except (OSError, EOFError):
        return
    if not content or guard.file_too_large(len(content)):
        return
    guard.register(len(content))
    yield _raw_file("", content)  # a raw gzip stream carries no member name
