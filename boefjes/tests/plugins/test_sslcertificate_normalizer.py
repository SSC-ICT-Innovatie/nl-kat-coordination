import datetime
import ipaddress

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed448, ed25519, rsa
from cryptography.x509.oid import NameOID

from boefjes.plugins.kat_ssl_certificates.normalize import read_certificates, run
from octopoes.models import Reference
from tests.loading import get_dummy_data

input_ooi = {
    "object_type": "Website",
    "scan_profile": "scan_profile_type='inherited' "
    "reference=Reference('Website|internet|134.209.85.72|tcp|443|https|internet|mispo.es') level=<ScanLevel.L2: 2>",
    "primary_key": "Website|internet|134.209.85.72|tcp|443|https|internet|mispo.es",
    "ip_service": {
        "ip_port": {
            "address": {"network": {"name": "internet"}, "address": "134.209.85.72"},
            "protocol": "tcp",
            "port": "443",
        },
        "service": {"name": "https"},
    },
    "hostname": {"network": {"name": "internet"}, "name": "mispo.es"},
    "certificate": "None",
}


def test_ssl_certificates_normalizer():
    output = list(run(input_ooi, get_dummy_data("ssl-certificates.txt")))
    assert len([ooi for ooi in output if hasattr(ooi, "object_type") and ooi.object_type == "X509Certificate"]) == 3
    for ooi in output:
        if hasattr(ooi, "object_type") and ooi.object_type == "X509Certificate":
            assert ooi.valid_from != ooi.valid_until


# Unit test for #5443 handling missing OrgName in certificates
def test_ssl_certificates_normalizer_without_issuer_organization():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example")])
    issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CA")])
    now = datetime.datetime.now(datetime.timezone.utc)

    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )

    pem = certificate.public_bytes(serialization.Encoding.PEM).decode()

    reference = Reference.from_str(input_ooi["primary_key"])
    certificates, _, _ = read_certificates(pem, reference)

    assert len(certificates) == 1
    assert certificates[0].issuer is None


# Test cases for EdDSA certificates (Ed25519 and Ed448)
def _create_ed_certificate(private_key):
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "test.example"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Organization"),
        ]
    )
    now = datetime.datetime.now(datetime.timezone.utc)

    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(private_key, algorithm=None)
    )

    return certificate.public_bytes(serialization.Encoding.PEM).decode()


def test_ssl_certificates_normalizer_ed25519():
    private_key = ed25519.Ed25519PrivateKey.generate()
    pem = _create_ed_certificate(private_key)

    reference = Reference.from_str(input_ooi["primary_key"])
    certificates, _, _ = read_certificates(pem, reference)

    assert len(certificates) == 1
    assert certificates[0].pk_algorithm == "AlgorithmType.EDDSA"
    assert certificates[0].pk_size is None
    assert len(certificates[0].pk_number) == 64


def test_ssl_certificates_normalizer_ed448():
    private_key = ed448.Ed448PrivateKey.generate()
    pem = _create_ed_certificate(private_key)

    reference = Reference.from_str(input_ooi["primary_key"])
    certificates, _, _ = read_certificates(pem, reference)

    assert len(certificates) == 1
    assert certificates[0].pk_algorithm == "AlgorithmType.EDDSA"
    assert certificates[0].pk_size is None
    assert len(certificates[0].pk_number) == 114


# Add test cases for Subject Alternative Names (SANs) in certificates
def _create_certificate_with_sans(sans):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "test.example"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Organization"),
        ]
    )

    now = datetime.datetime.now(datetime.timezone.utc)

    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName(sans), critical=False)
        .sign(private_key, algorithm=hashes.SHA256())
    )

    return certificate.public_bytes(serialization.Encoding.PEM).decode()


def test_ssl_certificates_normalizer_without_san():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example")])
    now = datetime.datetime.now(datetime.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )

    pem = certificate.public_bytes(serialization.Encoding.PEM).decode()
    reference = Reference.from_str(input_ooi["primary_key"])
    certificates, sans, hostnames = read_certificates(pem, reference)

    assert len(certificates) == 1
    assert sans == []
    assert hostnames == []


def test_ssl_certificates_normalizer_dns_san():
    pem = _create_certificate_with_sans([x509.DNSName("www.example.com")])

    reference = Reference.from_str(input_ooi["primary_key"])
    certificates, sans, hostnames = read_certificates(pem, reference)

    assert len(certificates) == 1
    assert len(sans) == 1
    assert len(hostnames) == 1
    assert hostnames[0].name == "www.example.com"


def test_ssl_certificates_normalizer_wildcard_san():
    pem = _create_certificate_with_sans([x509.DNSName("*.example.com")])

    reference = Reference.from_str(input_ooi["primary_key"])
    certificates, sans, hostnames = read_certificates(pem, reference)

    assert len(certificates) == 1
    assert len(sans) == 1
    assert len(hostnames) == 0
    assert sans[0].name == "*.example.com"


def test_ssl_certificates_normalizer_ipv4_san():
    pem = _create_certificate_with_sans([x509.IPAddress(ipaddress.IPv4Address("192.0.2.1"))])

    reference = Reference.from_str(input_ooi["primary_key"])
    certificates, sans, hostnames = read_certificates(pem, reference)

    assert len(certificates) == 1
    assert len(sans) == 1
    assert len(hostnames) == 0
    assert str(sans[0].address.tokenized.address) == "192.0.2.1"


def test_ssl_certificates_normalizer_ipv6_san():
    pem = _create_certificate_with_sans([x509.IPAddress(ipaddress.IPv6Address("2001:db8::1"))])

    reference = Reference.from_str(input_ooi["primary_key"])
    certificates, sans, hostnames = read_certificates(pem, reference)

    assert len(certificates) == 1
    assert len(sans) == 1
    assert len(hostnames) == 0
    assert str(sans[0].address.tokenized.address) == "2001:db8::1"


def test_ssl_certificates_normalizer_non_dns_sans_are_not_hostnames():
    pem = _create_certificate_with_sans(
        [x509.RFC822Name("admin@example.com"), x509.UniformResourceIdentifier("https://example.com")]
    )

    reference = Reference.from_str(input_ooi["primary_key"])
    certificates, sans, hostnames = read_certificates(pem, reference)

    assert len(certificates) == 1
    assert len(sans) == 0


def test_ssl_certificates_normalizer_self_signed_certificate():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example")])
    now = datetime.datetime.now(datetime.timezone.utc)

    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )

    pem = certificate.public_bytes(serialization.Encoding.PEM).decode()

    reference = Reference.from_str(input_ooi["primary_key"])
    certificates, _, _ = read_certificates(pem, reference)

    assert len(certificates) == 1
    assert certificates[0].subject == "test.example"
    assert certificates[0].issuer is None


def test_ssl_certificates_normalizer_unsupported_san_types_are_ignored():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example")])
    now = datetime.datetime.now(datetime.timezone.utc)

    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.RFC822Name("security@example.com"),
                    x509.UniformResourceIdentifier("https://example.com/security.txt"),
                ]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    pem = certificate.public_bytes(serialization.Encoding.PEM).decode()

    reference = Reference.from_str(input_ooi["primary_key"])
    certificates, sans, hostnames = read_certificates(pem, reference)

    assert len(certificates) == 1
    assert sans == []
    assert hostnames == []


# The certificate Boefje can operate on a Website belonging to another network.
# It should derive the network from the input/Website reference rather than hard-code it.
def test_ssl_certificates_normalizer_san_uses_certificate_network():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example")])
    now = datetime.datetime.now(datetime.timezone.utc)

    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("www.example.com")]), critical=False)
        .sign(private_key, hashes.SHA256())
    )

    pem = certificate.public_bytes(serialization.Encoding.PEM).decode()

    reference = Reference.from_str("Website|internal|192.0.2.0|tcp|443|https|internal|example.com")
    certificates, sans, hostnames = read_certificates(pem, reference)

    assert len(certificates) == 1
    assert len(sans) == 1
    assert len(hostnames) == 1
    assert hostnames[0].name == "www.example.com"
    assert hostnames[0].network.tokenized.name == "internal"


def test_ssl_certificates_normalizer_without_common_name():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Organization")])
    now = datetime.datetime.now(datetime.timezone.utc)

    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )

    pem = certificate.public_bytes(serialization.Encoding.PEM).decode()

    reference = Reference.from_str(input_ooi["primary_key"])
    certificates, _, _ = read_certificates(pem, reference)

    assert len(certificates) == 1
    assert certificates[0].subject is None


def _create_signed_certificate(subject_name, issuer_certificate, issuer_key, public_key):
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, subject_name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Organization"),
        ]
    )

    now = datetime.datetime.now(datetime.timezone.utc)

    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer_certificate.subject if issuer_certificate else subject)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(issuer_key, hashes.SHA256())
    )


# Test that certificates are in expected leaf-intermediate-root order.
def test_ssl_certificates_normalizer_certificate_chain():
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    root_certificate = _create_signed_certificate("Root CA", None, root_key, root_key.public_key())

    intermediate_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    intermediate_certificate = _create_signed_certificate(
        "Intermediate CA", root_certificate, root_key, intermediate_key.public_key()
    )

    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    leaf_certificate = _create_signed_certificate(
        "test.example", intermediate_certificate, intermediate_key, leaf_key.public_key()
    )

    pem = b"".join(
        certificate.public_bytes(serialization.Encoding.PEM)
        for certificate in (leaf_certificate, intermediate_certificate, root_certificate)
    )

    raw = b"Certificate chain\n" + pem + b"Certificate chain"

    output = list(run(input_ooi, raw))

    certificates = [ooi for ooi in output if getattr(ooi, "object_type", None) == "X509Certificate"]

    assert len(certificates) == 3

    leaf, intermediate, root = certificates

    assert leaf.subject == "test.example"
    assert intermediate.subject == "Intermediate CA"
    assert root.subject == "Root CA"

    assert leaf.signed_by == intermediate.reference
    assert intermediate.signed_by == root.reference
    assert root.signed_by is None
