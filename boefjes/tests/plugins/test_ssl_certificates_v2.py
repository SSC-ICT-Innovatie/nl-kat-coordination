import base64
import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, mldsa, rsa
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.x509.oid import NameOID

from boefjes.plugins.kat_ssl_certificates.normalize import run
from octopoes.models.ooi.certificate import TLSCertificateChain, X509CertificateV2
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import Finding
from octopoes.models.ooi.service import HostnameIPService

HOSTNAME_SERVICE_INPUT = {
    "object_type": "HostnameIPService",
    "primary_key": "HostnameIPService|internet|192.0.2.10|tcp|443|https|internet|example.com",
}

IP_SERVICE_INPUT = {
    "object_type": "IPService",
    "primary_key": "IPService|internet|192.0.2.10|tcp|443|https",
}


def make_cert(common_name: str, issuer_name: str | None = None, issuer_key=None, dns_names: list[str] | None = None):
    """Build a certificate; self-signed unless an issuer is given."""
    now = datetime.now(UTC)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    if issuer_name is None:
        issuer_name, issuer_key = common_name, key
    issuer_dn = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer_name)])

    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(issuer_dn)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=365))
    )
    if dns_names:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName(n) for n in dns_names]), critical=False
        )
    return builder.sign(issuer_key, SHA256()), key


def pem(cert: x509.Certificate) -> str:
    return cert.public_bytes(serialization.Encoding.PEM).decode()


def sni_output(*certs: x509.Certificate) -> bytes:
    """openssl s_client -showcerts output shape: one PEM block per entry,
    leaf first."""
    return (
        "depth=0 CN = example.com\n---\n"
        "Certificate chain\n"
        + "".join(f" {i} s:CN = {c.subject}\n   i:CN = {c.issuer}\n" for i, c in enumerate(certs))
        + "---\nServer certificate\n"
        + "".join(pem(c) for c in certs)
        + "---\nNo client certificate CA names sent\n---\n"
    ).encode()


@pytest.fixture
def root_and_leaf():
    root_cert, root_key = make_cert("Test Root CA")
    leaf_cert, _ = make_cert("example.com", issuer_name="Test Root CA", issuer_key=root_key, dns_names=["example.com"])
    return root_cert, root_key, leaf_cert


def test_sni_chain_and_certificates_emitted(root_and_leaf):
    root_cert, _, leaf_cert = root_and_leaf
    output = list(run(HOSTNAME_SERVICE_INPUT, sni_output(leaf_cert, root_cert)))

    chains = [o for o in output if isinstance(o, TLSCertificateChain)]
    certs = [o for o in output if isinstance(o, X509CertificateV2)]

    assert len(chains) == 1
    assert len(certs) == 2
    assert str(chains[0].hostname_ip_service) == HOSTNAME_SERVICE_INPUT["primary_key"]
    assert chains[0].ip_service is None
    assert chains[0].presented_certificates == [c.reference for c in certs]


def test_null_sni_chain_keyed_on_ip_service(root_and_leaf):
    root_cert, _, leaf_cert = root_and_leaf
    output = list(run(IP_SERVICE_INPUT, sni_output(leaf_cert, root_cert)))

    chains = [o for o in output if isinstance(o, TLSCertificateChain)]
    assert len(chains) == 1
    assert str(chains[0].ip_service) == IP_SERVICE_INPUT["primary_key"]
    assert chains[0].hostname_ip_service is None


def test_sans_declare_hostnames(root_and_leaf):
    """SAN names are declared as Hostnames plus their HostnameIPService pair
    (the presentation's own claim, converging with the discovery bit); no
    ResolvedHostname is synthesized."""
    root_cert, _, leaf_cert = root_and_leaf
    output = list(run(IP_SERVICE_INPUT, sni_output(leaf_cert, root_cert)))

    hostnames = [o for o in output if isinstance(o, Hostname)]
    pairs = [o for o in output if isinstance(o, HostnameIPService)]

    assert [h.name for h in hostnames] == ["example.com"]
    assert len(pairs) == 1
    assert str(pairs[0].ip_service) == IP_SERVICE_INPUT["primary_key"]
    assert pairs[0].hostname == hostnames[0].reference


def test_non_dns_safe_san_becomes_qualifier(root_and_leaf):
    """A SAN that is not a plain hostname (spaces, underscores) still shows
    up as a qualifier object; it is only skipped as a Hostname declaration."""
    root_cert, root_key, _leaf = root_and_leaf
    now = datetime.now(UTC)
    names = [x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, n)]) for n in ("not a name", "Test Root CA")]
    cert = (
        x509.CertificateBuilder()
        .subject_name(names[0])
        .issuer_name(names[1])
        .public_key(rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("not a name")]), critical=False)
        .sign(root_key, SHA256())
    )

    output = list(run(IP_SERVICE_INPUT, sni_output(cert)))

    assert [o.name for o in output if isinstance(o, Hostname)] == []
    qualifiers = [o for o in output if type(o).__name__ == "SubjectAlternativeNameQualifierV2"]
    assert [q.name for q in qualifiers] == ["not a name"]


def test_nothing_declared_when_name_is_not_dns_safe(root_and_leaf):
    root_cert, root_key, _leaf = root_and_leaf
    cert, _ = make_cert("Test Root CA", dns_names=[])
    output = list(run(IP_SERVICE_INPUT, sni_output(cert, root_cert)))

    assert not [o for o in output if isinstance(o, Hostname)]


def test_no_certificates_yields_nothing():
    assert list(run(HOSTNAME_SERVICE_INPUT, b"---\nNo client certificate CA names sent\n---\n")) == []


def test_signed_by_set_on_verified_issuer(root_and_leaf):
    root_cert, _, leaf_cert = root_and_leaf
    output = list(run(HOSTNAME_SERVICE_INPUT, sni_output(leaf_cert, root_cert)))

    certs = {c.subject: c for c in output if isinstance(c, X509CertificateV2)}
    assert certs["CN=example.com"].signed_by == certs["CN=Test Root CA"].reference
    assert certs["CN=Test Root CA"].signed_by is None


def test_duplicate_entries_dedup(root_and_leaf):
    root_cert, _, leaf_cert = root_and_leaf
    # The same certificate presented twice in one handshake.
    output = list(run(HOSTNAME_SERVICE_INPUT, sni_output(leaf_cert, root_cert, leaf_cert)))

    assert len([o for o in output if isinstance(o, X509CertificateV2)]) == 2
    assert len([o for o in output if isinstance(o, TLSCertificateChain)][0].presented_certificates) == 2


def test_identical_presentations_share_identity(root_and_leaf):
    """Re-observing the same presentation yields the identical chain primary
    key — provenance attaches to the existing object."""
    root_cert, _, leaf_cert = root_and_leaf
    raw = sni_output(leaf_cert, root_cert)
    first = list(run(HOSTNAME_SERVICE_INPUT, raw))[0]
    second = list(run(HOSTNAME_SERVICE_INPUT, raw))[0]

    assert first.primary_key == second.primary_key


def test_malformed_entry_yields_finding_with_proof(root_and_leaf):
    root_cert, _, leaf_cert = root_and_leaf
    raw = sni_output(leaf_cert).decode() + (
        " 1 s:CN = broken\n   i:CN = nobody\n"
        "-----BEGIN CERTIFICATE-----\nZm9vYmFy\n-----END CERTIFICATE-----\n"
    )
    output = list(run(HOSTNAME_SERVICE_INPUT, raw.encode()))

    chains = [o for o in output if isinstance(o, TLSCertificateChain)]
    findings = [o for o in output if isinstance(o, Finding)]

    # The chain contains only the parsed certificate; the broken entry is
    # evidenced by the finding, not by an object.
    assert len(chains) == 1
    assert len(chains[0].presented_certificates) == 1
    assert len(findings) == 1
    assert str(findings[0].finding_type) == "KATFindingType|KAT-UNPARSEABLE-CERTIFICATE"
    assert findings[0].ooi == chains[0].reference
    # No dynamic description; the predefined finding type carries the text.
    assert findings[0].description is None
    assert "position=1" in findings[0].proof
    assert "raw_hash=" in findings[0].proof


def test_certificate_v2_fields(root_and_leaf):
    root_cert, _, leaf_cert = root_and_leaf
    output = list(run(HOSTNAME_SERVICE_INPUT, sni_output(leaf_cert, root_cert)))

    leaf = [c for c in output if isinstance(c, X509CertificateV2) and c.subject == "CN=example.com"][0]
    der = base64.b64decode(leaf.raw)
    assert hashlib.sha256(der).hexdigest() == leaf.fingerprint
    assert x509.load_der_x509_certificate(der)
    assert leaf.pk_algorithm == "RSA"
    assert leaf.serial_number == format(leaf_cert.serial_number, "x")
    assert leaf.valid_until == leaf_cert.not_valid_after_utc.isoformat()


def test_ecdsa_certificate_algorithm(root_and_leaf):
    root_cert, root_key, _leaf = root_and_leaf
    now = datetime.now(UTC)
    names = [x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, n)]) for n in ("ec.example.com", "Test Root CA")]
    cert = (
        x509.CertificateBuilder()
        .subject_name(names[0])
        .issuer_name(names[1])
        .public_key(ec.generate_private_key(ec.SECP256R1()).public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=1))
        .sign(root_key, SHA256())
    )

    certs = [o for o in run(HOSTNAME_SERVICE_INPUT, sni_output(cert)) if isinstance(o, X509CertificateV2)]

    assert len(certs) == 1
    assert certs[0].pk_algorithm.startswith("EC ")


def test_mldsa_certificate_verifies_and_sets_signed_by():
    """An ML-DSA-signed chain gets the same signed_by treatment as RSA."""
    issuer_key = mldsa.MLDSA65PrivateKey.generate()
    now = datetime.now(UTC)
    names = [x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, n)]) for n in ("PQ Root", "pq.example.com")]

    def build(subject, issuer_dn, signing_key, public_key):
        return (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer_dn)
            .public_key(public_key)
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=1))
            .sign(signing_key, None)
        )

    root = build(names[0], names[0], issuer_key, issuer_key.public_key())
    leaf = build(names[1], names[0], issuer_key, mldsa.MLDSA65PrivateKey.generate().public_key())

    certs = {
        c.subject: c for c in run(HOSTNAME_SERVICE_INPUT, sni_output(leaf, root)) if isinstance(c, X509CertificateV2)
    }

    assert certs["CN=pq.example.com"].signed_by == certs["CN=PQ Root"].reference
    assert certs["CN=PQ Root"].pk_algorithm == "ML-DSA-65"
