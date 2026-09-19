"""Shared helpers for unpacker normalizers that decompress/extract a compound file (HAR, zip, tar,
gzip, …) into constituent raw files. These helpers enforce decompression-bomb limits and build the
discriminating mime-type tag that keeps every extracted raw's mime-type set unique per boefje_meta
(Bytes deduplicates raws on their mime-type set)."""

import hashlib

# Hard limits applied by every unpacker. They protect the normalizer runner against decompression
# bombs (zip/gzip bombs, HARs with thousands of entries) that would otherwise exhaust memory.
MAX_FILES = 1000  # maximum number of extracted files per unpack run
MAX_TOTAL_BYTES = 256 * 1024 * 1024  # maximum cumulative extracted size per unpack run (256 MiB)
MAX_FILE_BYTES = 64 * 1024 * 1024  # maximum size of a single extracted file (64 MiB)


class UnpackGuard:
    """Tracks how much has been extracted and decides whether extraction may continue.

    Usage in an unpacker loop::

        guard = UnpackGuard()
        for member in members:
            if guard.exhausted():
                break                       # count/total budget spent, stop iterating
            if guard.file_too_large(size):
                continue                    # skip this one oversized file, keep going
            content = read(member)
            guard.register(len(content))
            yield ...
    """

    def __init__(
        self, max_files: int = MAX_FILES, max_total_bytes: int = MAX_TOTAL_BYTES, max_file_bytes: int = MAX_FILE_BYTES
    ):
        self.max_files = max_files
        self.max_total_bytes = max_total_bytes
        self.max_file_bytes = max_file_bytes
        self.files = 0
        self.total_bytes = 0

    def exhausted(self) -> bool:
        return self.files >= self.max_files or self.total_bytes >= self.max_total_bytes

    def file_too_large(self, size: int) -> bool:
        return size > self.max_file_bytes

    def register(self, size: int) -> None:
        self.files += 1
        self.total_bytes += size


def discriminator_tag(prefix: str, content: bytes) -> str:
    """A content-addressed mime tag (e.g. ``har-resource/<sha256[:16]>``) that makes the extracted
    raw's mime-type set unique. Identical content yields the same tag, so Bytes naturally deduplicates
    identical extracted files. No normalizer consumes this synthetic tag, so it is inert for routing."""
    return f"{prefix}/{hashlib.sha256(content).hexdigest()[:16]}"


def normalize_mime_type(mime_type: str | None) -> str:
    """Strip charset/parameters from a Content-Type (``text/html; charset=utf-8`` -> ``text/html``)
    so downstream normalizers match on the bare type. Falls back to ``application/octet-stream``."""
    if not mime_type:
        return "application/octet-stream"
    bare = mime_type.split(";")[0].strip().lower()
    return bare or "application/octet-stream"
