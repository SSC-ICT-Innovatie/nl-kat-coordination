from boefjes.plugins.kat_webpage_analysis.main import do_request, is_same_resource


class FakeResponse:
    def __init__(self, status_code, url, location=None, body=b""):
        self.status_code = status_code
        self.url = url
        self.headers = {"location": location} if location else {}
        self.content = body

    @property
    def is_redirect(self):
        return 300 <= self.status_code < 400 and "location" in self.headers


class FakeSession:
    """Returns the queued response whose url matches the requested url."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requested = []

    def get(self, url, **kwargs):
        self.requested.append(url)
        for response in self.responses:
            if response.url == url:
                return response
        raise AssertionError(f"unexpected request to {url}")


def test_follows_canonical_same_resource_redirect_dropping_default_port():
    # The boefje requests the URL with an explicit :443; the server canonicalises
    # to the port-less form. Same resource -> follow and return the real body.
    session = FakeSession(
        [
            FakeResponse(301, "https://example.com:443/", location="https://example.com/"),
            FakeResponse(200, "https://example.com/", body=b"<html>real</html>"),
        ]
    )

    response = do_request("example.com:443", session, "https://example.com:443/", "OpenKAT")

    assert response.status_code == 200
    assert response.content == b"<html>real</html>"
    assert session.requested == ["https://example.com:443/", "https://example.com/"]


def test_follows_self_redirect_ignoring_query():
    # A cache/security warm-up 301 to the same path with a marker query.
    session = FakeSession(
        [
            FakeResponse(302, "https://example.com:443/", location="https://example.com:443/?nocache=1"),
            FakeResponse(200, "https://example.com:443/?nocache=1", body=b"<html>ok</html>"),
        ]
    )

    response = do_request("example.com:443", session, "https://example.com:443/", "OpenKAT")

    assert response.status_code == 200


def test_does_not_follow_cross_url_redirect():
    # apex -> www is a different resource; leave the 301 so the target is
    # discovered and scanned separately. Only one request is made.
    session = FakeSession([FakeResponse(301, "https://example.com:443/", location="https://www.example.com/")])

    response = do_request("example.com:443", session, "https://example.com:443/", "OpenKAT")

    assert response.status_code == 301
    assert session.requested == ["https://example.com:443/"]


def test_does_not_follow_http_to_https_redirect():
    session = FakeSession([FakeResponse(301, "http://example.com:80/", location="https://example.com/")])

    response = do_request("example.com:80", session, "http://example.com:80/", "OpenKAT")

    assert response.status_code == 301


def test_redirect_loop_is_bounded():
    responses = [
        FakeResponse(301, f"https://example.com:443/?n={n}", location=f"https://example.com:443/?n={n + 1}")
        for n in range(10)
    ]
    session = FakeSession(
        [FakeResponse(301, "https://example.com:443/", location="https://example.com:443/?n=0")] + responses
    )

    response = do_request("example.com:443", session, "https://example.com:443/", "OpenKAT")

    # Bounded: does not loop forever, returns the last redirect it stopped at.
    assert response.is_redirect
    assert len(session.requested) <= 1 + 5


def test_is_same_resource():
    assert is_same_resource("https://a.com:443/", "https://a.com/")
    assert is_same_resource("http://a.com:80/", "http://a.com/")
    assert is_same_resource("https://a.com/", "https://a.com/?x=1")
    assert not is_same_resource("https://a.com/", "https://www.a.com/")
    assert not is_same_resource("http://a.com/", "https://a.com/")
    assert not is_same_resource("https://a.com/", "https://a.com/other")
    assert not is_same_resource("https://a.com:443/", "https://a.com:8443/")
