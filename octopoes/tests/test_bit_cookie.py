from bits.check_cookie.check_cookie import run

from octopoes.models import Reference
from octopoes.models.ooi.web import Cookie

DOMAIN = Reference.from_str("Hostname|internet|example.com")


def _cookie(**kwargs):
    kwargs.setdefault("name", "sid")
    return Cookie(domain=DOMAIN, **kwargs)


def _findings(cookie):
    return [result for result in run(cookie, [], {}) if result.object_type == "Finding"]


def test_fully_secure_cookie_is_clean():
    assert _findings(_cookie(secure_only=True, http_only=True, same_site="Lax")) == []


def test_bare_cookie_reports_all_three_attributes():
    (finding,) = _findings(_cookie())
    assert "Secure attribute is not set" in finding.description
    assert "HttpOnly attribute is not set" in finding.description
    assert "SameSite attribute is set" in finding.description


def test_only_missing_secure_is_reported():
    (finding,) = _findings(_cookie(http_only=True, same_site="Strict"))
    assert "Secure attribute is not set" in finding.description
    assert "HttpOnly" not in finding.description


def test_samesite_none_without_secure_is_flagged():
    (finding,) = _findings(_cookie(http_only=True, same_site="None"))
    assert "SameSite=None" in finding.description


def test_samesite_none_with_secure_is_allowed():
    assert _findings(_cookie(secure_only=True, http_only=True, same_site="None")) == []


def test_host_prefix_with_non_root_path_is_flagged():
    cookie = _cookie(name="__Host-sid", path="/app", secure_only=True, http_only=True, same_site="Lax")
    (finding,) = _findings(cookie)
    assert "__Host-" in finding.description


def test_host_prefix_satisfied_is_clean():
    cookie = _cookie(name="__Host-sid", path="/", secure_only=True, http_only=True, same_site="Lax")
    assert _findings(cookie) == []


def test_secure_prefix_requires_secure():
    (finding,) = _findings(_cookie(name="__Secure-sid", http_only=True, same_site="Lax"))
    assert "__Secure-" in finding.description


def test_finding_is_deterministic():
    first = _findings(_cookie())[0]
    second = _findings(_cookie())[0]
    assert first.model_dump() == second.model_dump()
