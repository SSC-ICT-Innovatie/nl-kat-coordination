import json

from boefjes.worker.job_models import NormalizerMeta
from octopoes.models.ooi.web import Cookie, HTTPHeader
from tests.loading import get_dummy_data


def _run(normalizer_runner, headers):
    meta = NormalizerMeta.model_validate_json(get_dummy_data("headers-normalize.json"))
    output = normalizer_runner.run(meta, json.dumps(headers).encode())

    return [ooi for observation in output.observations for ooi in observation.results]


def _headers(oois):
    return {ooi.key: ooi.value for ooi in oois if isinstance(ooi, HTTPHeader)}


def _cookies(oois):
    return {ooi.name: ooi for ooi in oois if isinstance(ooi, Cookie)}


def test_legacy_dict_shape_passes_headers_through(normalizer_runner):
    oois = _run(normalizer_runner, {"Server": "nginx/1.18.0", "Content-Type": "text/html"})
    headers = _headers(oois)

    assert headers == {"Server": "nginx/1.18.0", "Content-Type": "text/html"}


def test_volatile_header_value_is_redacted_but_header_stays(normalizer_runner):
    oois = _run(
        normalizer_runner, [["Date", "Tue, 03 Jan 2023 10:16:45 GMT"], ["CF-Ray", "8f2b3-AMS"], ["Server", "nginx"]]
    )
    headers = _headers(oois)

    assert headers["Date"] == "<redacted>"
    assert headers["CF-Ray"] == "<redacted>"
    assert headers["Server"] == "nginx"


def test_multiple_set_cookie_headers_fold_into_one_canonical_header(normalizer_runner):
    oois = _run(
        normalizer_runner,
        [["Set-Cookie", "PHPSESSID=abc123; Path=/; HttpOnly"], ["Set-Cookie", "lang=en; Path=/; Secure; SameSite=Lax"]],
    )

    headers = _headers(oois)
    assert headers["Set-Cookie"] == "PHPSESSID=<redacted>; Path=/; HttpOnly, lang=en; Path=/; Secure; SameSite=Lax"

    cookies = _cookies(oois)
    assert set(cookies) == {"PHPSESSID", "lang"}
    assert cookies["PHPSESSID"].http_only and not cookies["PHPSESSID"].secure_only
    assert cookies["lang"].secure_only and cookies["lang"].same_site == "Lax"
    assert cookies["lang"].host_only and str(cookies["lang"].domain).endswith("mispo.es")


def test_volatile_values_produce_identical_oois(normalizer_runner):
    # The load-bearing test for #213: two observations that differ only in
    # token values must produce a byte-identical OOI set.
    def observation(session_token, cf_ray, date):
        return [
            ["Date", date],
            ["CF-Ray", cf_ray],
            ["Server", "nginx"],
            ["Set-Cookie", f"sessionid={session_token}; Path=/; Expires={date}; HttpOnly"],
        ]

    first = _run(normalizer_runner, observation("aaa111", "ray-1", "Tue, 03 Jan 2023 10:16:45 GMT"))
    second = _run(normalizer_runner, observation("bbb222", "ray-2", "Wed, 04 Jan 2023 11:17:46 GMT"))

    assert [ooi.model_dump() for ooi in first] == [ooi.model_dump() for ooi in second]


def test_legacy_joined_set_cookie_is_resplit_across_expires_comma(normalizer_runner):
    joined = (
        "has_recent_activity=1; Path=/; Expires=Tue, 28 Feb 2023 14:21:36 GMT; Secure; HttpOnly; "
        "SameSite=Lax, gh_sess=xxxxxxx; Path=/; Secure; HttpOnly; SameSite=Lax"
    )
    oois = _run(normalizer_runner, {"Set-Cookie": joined})

    cookies = _cookies(oois)
    assert set(cookies) == {"has_recent_activity", "gh_sess"}


def test_max_age_wins_over_expires_and_buckets_lifetime(normalizer_runner):
    oois = _run(
        normalizer_runner,
        [
            ["Date", "Tue, 03 Jan 2023 10:16:45 GMT"],
            ["Set-Cookie", "a=1; Max-Age=3600; Expires=Thu, 02 Feb 2023 10:16:45 GMT"],
            ["Set-Cookie", "b=2; Expires=Thu, 02 Feb 2023 10:16:45 GMT"],
            ["Set-Cookie", "c=3"],
        ],
    )

    cookies = _cookies(oois)
    assert cookies["a"].persistent and cookies["a"].lifetime == "<1d"
    assert cookies["b"].persistent and cookies["b"].lifetime == "<30d"
    assert not cookies["c"].persistent and cookies["c"].lifetime == "session"


def test_broken_expires_is_ignored_not_a_finding(normalizer_runner):
    # RFC 6265 5.2.1: an Expires that fails to parse means the attribute is ignored;
    # browsers keep the cookie. No finding, cookie becomes a session cookie.
    oois = _run(normalizer_runner, {"Set-Cookie": "a=1; Expires=sdsd 28 Feb 2023; Path=/"})

    cookies = _cookies(oois)
    assert not cookies["a"].persistent
    assert all(ooi.object_type in ("HTTPHeader", "Cookie", "Hostname") for ooi in oois)


def test_domain_mismatch_is_treated_as_host_only(normalizer_runner):
    # RFC 6265 5.3 p6 — and it keeps a scanned server from injecting arbitrary
    # Hostname OOIs into the graph.
    oois = _run(normalizer_runner, {"Set-Cookie": "evil=1; Domain=evil.com"})

    cookies = _cookies(oois)
    assert cookies["evil"].host_only
    assert str(cookies["evil"].domain) == "Hostname|internet|mispo.es"
    assert not any(str(ooi.reference) == "Hostname|internet|evil.com" for ooi in oois)


def test_valid_parent_domain_mints_domain_cookie_and_hostname(normalizer_runner):
    oois = _run(normalizer_runner, {"Set-Cookie": "shared=1; Domain=.mispo.es"})

    cookies = _cookies(oois)
    assert not cookies["shared"].host_only
    assert str(cookies["shared"].domain) == "Hostname|internet|mispo.es"


def test_nameless_cookie_is_ignored(normalizer_runner):
    oois = _run(normalizer_runner, {"Set-Cookie": "justavalue"})

    assert _cookies(oois) == {}


def test_pipe_in_cookie_name_does_not_mint_a_cookie(normalizer_runner):
    # A pipe would corrupt the natural key (reference separator).
    oois = _run(normalizer_runner, {"Set-Cookie": "bad|name=1; Path=/"})

    assert _cookies(oois) == {}


def test_stable_meaningful_cookie_value_is_kept(normalizer_runner):
    # HAProxy route cookies carry stable topology signal; only curated names
    # are redacted.
    oois = _run(normalizer_runner, {"Set-Cookie": "SERVERID=backend1; Path=/"})

    assert "SERVERID=backend1" in _headers(oois)["Set-Cookie"]


def test_repeated_headers_fold_into_one_joined_value(normalizer_runner):
    # HTTPHeader identity is (resource, key); repeated headers must merge into
    # one value like the legacy dict shape did, not last-write-wins.
    oois = _run(normalizer_runner, [["Via", "1.1 proxy-a"], ["Via", "1.1 proxy-b"], ["Server", "nginx"]])

    headers = _headers(oois)
    assert headers["Via"] == "1.1 proxy-a, 1.1 proxy-b"


def test_output_is_deterministic(normalizer_runner):
    headers = [["Set-Cookie", "sessionid=tok; Path=/; Secure"], ["Server", "nginx"]]

    first = _run(normalizer_runner, headers)
    second = _run(normalizer_runner, headers)

    assert [ooi.model_dump() for ooi in first] == [ooi.model_dump() for ooi in second]
