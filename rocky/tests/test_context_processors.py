from tools.context_processors import languages


def test_language_links_swap_language_prefix(rf):
    request = rf.get("/en/test/objects/?observed_at=2024-01-01")
    request.LANGUAGE_CODE = "en"

    links = dict(languages(request)["language_links"])

    assert links["nl"] == "/nl/test/objects/?observed_at=2024-01-01"
    assert links["en"] == "/en/test/objects/?observed_at=2024-01-01"


def test_language_links_on_unprefixed_url(rf):
    request = rf.get("/account/login/")
    request.LANGUAGE_CODE = "en"

    links = dict(languages(request)["language_links"])

    assert links["nl"] == "/nl/"
