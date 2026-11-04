from boefjes.plugins.unpack_common import UnpackGuard, discriminator_tag, normalize_mime_type


def test_guard_stops_on_file_count():
    guard = UnpackGuard(max_files=2)

    assert not guard.exhausted()
    guard.register(1)
    assert not guard.exhausted()
    guard.register(1)
    assert guard.exhausted()  # two files registered, budget spent


def test_guard_stops_on_total_bytes():
    guard = UnpackGuard(max_total_bytes=10)

    guard.register(9)
    assert not guard.exhausted()
    guard.register(1)
    assert guard.exhausted()


def test_guard_flags_single_oversized_file():
    guard = UnpackGuard(max_file_bytes=100)

    assert guard.file_too_large(101)
    assert not guard.file_too_large(100)


def test_discriminator_is_content_addressed():
    tag_a = discriminator_tag("har-resource", b"same")
    tag_b = discriminator_tag("har-resource", b"same")
    tag_c = discriminator_tag("har-resource", b"different")

    assert tag_a == tag_b  # identical content -> identical tag (Bytes deduplicates)
    assert tag_a != tag_c
    assert tag_a.startswith("har-resource/")


def test_normalize_mime_type_strips_parameters_and_defaults():
    assert normalize_mime_type("text/html; charset=utf-8") == "text/html"
    assert normalize_mime_type("APPLICATION/JavaScript") == "application/javascript"
    assert normalize_mime_type(None) == "application/octet-stream"
    assert normalize_mime_type("") == "application/octet-stream"
