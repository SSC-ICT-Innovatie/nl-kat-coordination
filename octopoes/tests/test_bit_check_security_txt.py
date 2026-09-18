from bits.check_security_txt.check_security_txt import run

from octopoes.models import Reference
from octopoes.models.ooi.web import SecurityTXT

WEBSITE_REF = Reference.from_str("Website|internet|example.com|192.0.2.1")


def _sectxt(content):
    return SecurityTXT(website=WEBSITE_REF, url=WEBSITE_REF, security_txt=content)


def _findings(sectxt):
    return [r for r in run(sectxt, [], {}) if r.object_type == "Finding"]


def test_valid_security_txt():
    content = "Contact: mailto:security@example.com\nExpires: 2030-12-31T23:59:59.000Z\nEncryption: https://example.com/pgp.asc\n"
    assert _findings(_sectxt(content)) == []


def test_missing_contact():
    content = "Expires: 2030-12-31T23:59:59.000Z\n"
    findings = _findings(_sectxt(content))
    assert any("Contact" in f.description for f in findings)


def test_missing_expires():
    content = "Contact: mailto:security@example.com\n"
    findings = _findings(_sectxt(content))
    assert any("Expires" in f.description for f in findings)


def test_expired_expires():
    content = "Contact: mailto:security@example.com\nExpires: 2020-01-01T00:00:00.000Z\n"
    findings = _findings(_sectxt(content))
    assert any("past" in f.description for f in findings)


def test_missing_encryption_recommended():
    content = "Contact: mailto:security@example.com\nExpires: 2030-12-31T23:59:59.000Z\n"
    findings = _findings(_sectxt(content))
    assert any("Encryption" in f.description for f in findings)


def test_unknown_field_ignored():
    """RFC 9116 §2.2: unknown fields MUST be ignored, not flagged."""
    content = "Contact: mailto:security@example.com\nExpires: 2030-12-31T23:59:59.000Z\nBogus: value\n"
    findings = _findings(_sectxt(content))
    assert findings == []


def test_empty_content():
    assert _findings(_sectxt("")) == []


def test_comments_ignored():
    content = (
        "# This is a comment\n"
        "Contact: mailto:security@example.com\n"
        "Expires: 2030-12-31T23:59:59.000Z\n"
        "Encryption: https://example.com/pgp.asc\n"
    )
    assert _findings(_sectxt(content)) == []


def test_pgp_signed_content():
    content = """Contact: mailto:security@example.com
Expires: 2030-12-31T23:59:59.000Z
Encryption: https://example.com/pgp.asc
-----BEGIN PGP SIGNATURE-----
iQIzBAEBCAAdFiEE12345
-----END PGP SIGNATURE-----
"""
    assert _findings(_sectxt(content)) == []


def test_invalid_expires_date():
    content = "Contact: mailto:security@example.com\nExpires: not-a-date\n"
    findings = _findings(_sectxt(content))
    assert any("not a valid" in f.description for f in findings)
