import base64
import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.x509.oid import NameOID

from boefjes.plugins.kat_ssl_certificates import normalize
from boefjes.plugins.kat_ssl_certificates.normalize import run
from octopoes.models.ooi.certificate import TLSCertificateChain, X509CertificateV2
from octopoes.models.ooi.findings import Finding


def host_input(name: str) -> dict:
    return {
        "object_type": "HostnameIPService",
        "primary_key": f"HostnameIPService|internet|192.0.2.10|tcp|443|https|internet|{name}",
    }


HOSTNAME_SERVICE_INPUT = host_input("example.com")

IP_SERVICE_INPUT = {"object_type": "IPService", "primary_key": "IPService|internet|192.0.2.10|tcp|443|https"}


def make_cert(
    common_name: str,
    *,
    issuer_cert=None,
    issuer_key=None,
    not_before: datetime | None = None,
    not_after: datetime | None = None,
    dns_names: list[str] | None = None,
):
    """Build a certificate; self-signed unless an issuer is given."""
    now = datetime.now(UTC)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    if issuer_cert is None:
        issuer_cert, issuer_key = name, key
    issuer_dn = issuer_cert.subject if isinstance(issuer_cert, x509.Certificate) else issuer_cert

    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(issuer_dn)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before or now - timedelta(days=1))
        .not_valid_after(not_after or now + timedelta(days=30))
    )
    if dns_names:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName(n) for n in dns_names]), critical=False
        )
    return builder.sign(issuer_key, SHA256()), key


def pem(cert: x509.Certificate) -> str:
    return cert.public_bytes(serialization.Encoding.PEM).decode()


def sni_output(*certs: x509.Certificate) -> bytes:
    return (
        "Certificate chain\n"
        + "".join(f" {i} s:CN = {c.subject}\n   i:CN = {c.issuer}\n" for i, c in enumerate(certs))
        + "---\nServer certificate\n"
        + "".join(pem(c) for c in certs)
        + "---\nNo client certificate CA names sent\n---\n"
    ).encode()


def oois_for(*certs: x509.Certificate, input_ooi=None):
    return list(run(input_ooi or HOSTNAME_SERVICE_INPUT, sni_output(*certs)))


def finding_types(output) -> dict[str, list[Finding]]:
    types: dict[str, list[Finding]] = {}
    for ooi in output:
        if isinstance(ooi, Finding):
            types.setdefault(str(ooi.finding_type), []).append(ooi)
    return types


@pytest.fixture
def no_trust_store(monkeypatch):
    monkeypatch.setattr(normalize, "_trust_anchors", lambda: ())


@pytest.fixture
def trust_store(monkeypatch):
    """A trust store holding exactly the root the tests build."""
    store = {}

    def _anchors():
        return tuple(store.values())

    monkeypatch.setattr(normalize, "_trust_anchors", _anchors)
    return store


def test_missing_intermediate_fires_on_chain(trust_store):
    root, root_key = make_cert("Test Root CA")
    trust_store[hashlib.sha256(root.public_bytes(serialization.Encoding.DER)).hexdigest()] = root
    intermediate, intermediate_key = make_cert("Test Intermediate CA", issuer_cert=root, issuer_key=root_key)
    leaf, _ = make_cert("example.com", issuer_cert=intermediate, issuer_key=intermediate_key)

    findings = finding_types(oois_for(leaf))

    # The intermediate is not presented and the root only anchors itself:
    # the presentation is incomplete.
    assert "KATFindingType|KAT-INCOMPLETE-CERTIFICATE-CHAIN" in findings
    description = findings["KATFindingType|KAT-INCOMPLETE-CERTIFICATE-CHAIN"][0].description
    assert "example.com" in description  # codeql[py/incomplete-url-substring-sanitization]


def test_full_chain_with_trusted_root_is_complete(trust_store):
    root, root_key = make_cert("Test Root CA")
    trust_store[hashlib.sha256(root.public_bytes(serialization.Encoding.DER)).hexdigest()] = root
    intermediate, intermediate_key = make_cert("Test Intermediate CA", issuer_cert=root, issuer_key=root_key)
    leaf, _ = make_cert("example.com", issuer_cert=intermediate, issuer_key=intermediate_key)

    findings = finding_types(oois_for(leaf, intermediate))

    assert "KATFindingType|KAT-INCOMPLETE-CERTIFICATE-CHAIN" not in findings


def test_extra_cross_sign_by_retired_root_does_not_flag_the_presentation(trust_store):
    # hasecon's M2 (#5585): leaf -> intermediate -> trusted root, PLUS a
    # cross-sign by a root that is not (or no longer) trusted. Every client
    # validates the leaf and silently ignores the extra certificate; only
    # the leaf's path to a root decides incompleteness.
    trusted_root, trusted_root_key = make_cert("Trusted Root CA")
    trust_store[hashlib.sha256(trusted_root.public_bytes(serialization.Encoding.DER)).hexdigest()] = trusted_root
    intermediate, intermediate_key = make_cert(
        "Test Intermediate CA", issuer_cert=trusted_root, issuer_key=trusted_root_key
    )
    leaf, _ = make_cert("example.com", issuer_cert=intermediate, issuer_key=intermediate_key)

    retired_root, retired_root_key = make_cert("Retired Root CA")
    cross_sign, _ = make_cert("Test Intermediate CA", issuer_cert=retired_root, issuer_key=retired_root_key)

    findings = finding_types(oois_for(leaf, cross_sign))

    assert "KATFindingType|KAT-INCOMPLETE-CERTIFICATE-CHAIN" not in findings


def test_root_in_store_anchors_directly(trust_store):
    root, root_key = make_cert("Test Root CA")
    trust_store[hashlib.sha256(root.public_bytes(serialization.Encoding.DER)).hexdigest()] = root
    intermediate, intermediate_key = make_cert("Test Intermediate CA", issuer_cert=root, issuer_key=root_key)
    leaf, _ = make_cert("example.com", issuer_cert=intermediate, issuer_key=intermediate_key)

    # The intermediate alone is enough: its issuer is a trusted root.
    findings = finding_types(oois_for(leaf, intermediate))

    assert "KATFindingType|KAT-INCOMPLETE-CERTIFICATE-CHAIN" not in findings


def test_self_signed_leaf_fires_self_signed_not_incomplete(trust_store):
    # A store with only an unrelated root: the self-signed leaf anchors nowhere.
    unrelated, _ = make_cert("Unrelated Root CA")
    trust_store[hashlib.sha256(unrelated.public_bytes(serialization.Encoding.DER)).hexdigest()] = unrelated
    self_signed, _ = make_cert("admin.internal", dns_names=["admin.internal"])

    findings = finding_types(oois_for(self_signed))

    # One meaning per finding type: a self-signed leaf is not an incomplete
    # chain, it is its own finding.
    assert "KATFindingType|KAT-SELF-SIGNED-CERTIFICATE" in findings
    assert "KATFindingType|KAT-INCOMPLETE-CERTIFICATE-CHAIN" not in findings


def test_trusted_root_presented_alone_fires_nothing(trust_store):
    # A trust anchor presented by itself is neither self-signed (excluded)
    # nor incomplete (it anchors). Its name covers the presentation's to
    # keep the mismatch check out of the way.
    root, _ = make_cert("example.com", dns_names=["example.com"])
    trust_store[hashlib.sha256(root.public_bytes(serialization.Encoding.DER)).hexdigest()] = root

    findings = finding_types(oois_for(root))

    assert findings == {}


def test_no_trust_store_assesses_nothing(no_trust_store):
    root, root_key = make_cert("Test Root CA")
    leaf, _ = make_cert("example.com", issuer_cert=root, issuer_key=root_key, dns_names=["example.com"])

    findings = finding_types(oois_for(leaf, root))

    assert findings == {}


def test_expired_certificate_fires_on_the_certificate(trust_store):
    now = datetime.now(UTC)
    expired_cert, _ = make_cert("example.com", not_before=now - timedelta(days=200), not_after=now - timedelta(days=1))

    findings = finding_types(oois_for(expired_cert))

    assert "KATFindingType|KAT-CERTIFICATE-EXPIRED" in findings
    finding = findings["KATFindingType|KAT-CERTIFICATE-EXPIRED"][0]
    # About the certificate, not the chain.
    assert str(finding.ooi).startswith("X509CertificateV2|")


def test_certificate_past_renewal_point_fires_expiring_soon(trust_store):
    now = datetime.now(UTC)
    # A 90-day lifetime: the renewal point is 30 days before expiry, minus
    # the 2-day detection lag, so it fires under 28 days remaining.
    cert, _ = make_cert("example.com", not_before=now - timedelta(days=70), not_after=now + timedelta(days=20))

    findings = finding_types(oois_for(cert))

    assert "KATFindingType|KAT-CERTIFICATE-EXPIRING-SOON" in findings
    description = findings["KATFindingType|KAT-CERTIFICATE-EXPIRING-SOON"][0].description
    assert "renewal point" in description


def test_certificate_before_renewal_point_does_not_fire(trust_store):
    now = datetime.now(UTC)
    cert, _ = make_cert("example.com", not_before=now - timedelta(days=50), not_after=now + timedelta(days=40))

    findings = finding_types(oois_for(cert))

    assert "KATFindingType|KAT-CERTIFICATE-EXPIRING-SOON" not in findings
    assert "KATFindingType|KAT-CERTIFICATE-EXPIRED" not in findings


def test_certificate_shorter_than_detection_lag_never_fires_expiring_soon(trust_store):
    now = datetime.now(UTC)
    # A six-day certificate: the renewal point is inside the detection lag,
    # so it can never be observed in time; expiry itself is the signal.
    cert, _ = make_cert("example.com", not_before=now - timedelta(days=3), not_after=now + timedelta(days=2, hours=23))

    findings = finding_types(oois_for(cert))

    assert "KATFindingType|KAT-CERTIFICATE-EXPIRING-SOON" not in findings


def test_hostname_mismatch_fires_on_chain(no_trust_store):
    # The leaf covers api.example.com; the presentation claims example.com.
    leaf, _ = make_cert("api.example.com", dns_names=["api.example.com"])

    findings = finding_types(oois_for(leaf))

    assert "KATFindingType|KAT-SSL-CERT-HOSTNAME-MISMATCH" in findings
    finding = findings["KATFindingType|KAT-SSL-CERT-HOSTNAME-MISMATCH"][0]
    assert str(finding.ooi).startswith("TLSCertificateChain|")


def test_hostname_covered_by_wildcard_does_not_fire(no_trust_store):
    # RFC 6125: a wildcard covers exactly one label, so *.example.com
    # covers www.example.com but not example.com itself.
    leaf, _ = make_cert("example.com", dns_names=["*.example.com"])

    findings = finding_types(oois_for(leaf, input_ooi=host_input("www.example.com")))

    assert "KATFindingType|KAT-SSL-CERT-HOSTNAME-MISMATCH" not in findings

    findings = finding_types(oois_for(leaf, input_ooi=host_input("example.com")))

    assert "KATFindingType|KAT-SSL-CERT-HOSTNAME-MISMATCH" in findings


def test_hostname_covered_by_san_does_not_fire(no_trust_store):
    leaf, _ = make_cert("example.com", dns_names=["example.com", "www.example.com"])

    findings = finding_types(oois_for(leaf))

    assert "KATFindingType|KAT-SSL-CERT-HOSTNAME-MISMATCH" not in findings


def test_sanless_certificate_fires_mismatch(no_trust_store):
    # Modern clients ignore the common name (RFC 6125 leaves the CN to
    # legacy clients), so a certificate without a SAN is rejected regardless
    # of its CN — matching V1, where a SAN-less certificate fired the
    # mismatch. Even a CN identical to the visited name does not save it.
    for cn in ("example.com", "Example.com"):
        leaf, _ = make_cert(cn)
        findings = finding_types(oois_for(leaf))
        assert "KATFindingType|KAT-SSL-CERT-HOSTNAME-MISMATCH" in findings, cn


def test_non_wildcard_san_does_not_cover_sibling_subdomains(no_trust_store):
    # A SAN without the * prefix is not a wildcard: before the check, a SAN
    # m.example.com matched www.example.com (wildcard[2:] on a non-wildcard
    # happens to equal the parent domain) and suppressed the mismatch.
    leaf, _ = make_cert("m.example.com", dns_names=["m.example.com"])

    findings = finding_types(oois_for(leaf, input_ooi=host_input("www.example.com")))

    assert "KATFindingType|KAT-SSL-CERT-HOSTNAME-MISMATCH" in findings


def test_null_sni_presentation_is_never_assessed_for_mismatch(no_trust_store):
    # A connection without a server name claims nothing about a name.
    leaf, _ = make_cert("example.com", dns_names=["*.other.example.com"])

    findings = finding_types(oois_for(leaf, input_ooi=IP_SERVICE_INPUT))

    assert "KATFindingType|KAT-SSL-CERT-HOSTNAME-MISMATCH" not in findings


def test_findings_reference_the_built_objects(no_trust_store):
    # The findings bind to the same OOI objects the normalizer built.
    root, root_key = make_cert("Test Root CA")
    intermediate, intermediate_key = make_cert("Test Intermediate CA", issuer_cert=root, issuer_key=root_key)
    leaf, _ = make_cert("unrelated.example.com", issuer_cert=intermediate, issuer_key=intermediate_key)

    output = oois_for(leaf)
    chains = [o for o in output if isinstance(o, TLSCertificateChain)]
    certs = [o for o in output if isinstance(o, X509CertificateV2)]
    findings = [o for o in output if isinstance(o, Finding)]

    mismatch = next(f for f in findings if "HOSTNAME-MISMATCH" in str(f.finding_type))
    assert mismatch.ooi == chains[0].reference
    # The leaf's reference equals the emitted certificate's.
    leaf_ooi = next(c for c in certs if base64.b64decode(c.raw) == leaf.public_bytes(serialization.Encoding.DER))
    assert leaf_ooi.fingerprint[:16] in mismatch.description
