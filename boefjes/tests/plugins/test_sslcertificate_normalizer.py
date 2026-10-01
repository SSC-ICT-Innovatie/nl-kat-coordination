import datetime

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed448, ed25519
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
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


# Test cases for EdDSA certificates (Ed25519 and Ed448)
def _create_ed_certificate(private_key):
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "test.example"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Organization"),
        ]
    )
    now = datetime.datetime.now(datetime.timezone.utc)
# Unit test for #5443 handling missing OrgName in certificates
def test_ssl_certificates_normalizer_without_issuer_organization():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example")])
    issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CA")])

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
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )

    pem = certificate.public_bytes(serialization.Encoding.PEM).decode()

    reference = Reference.from_str(input_ooi["primary_key"])
    certificates, _, _ = read_certificates(pem, reference)

    assert len(certificates) == 1
    assert certificates[0].pk_algorithm == "AlgorithmType.EDDSA"
    assert certificates[0].pk_size is None
    assert len(certificates[0].pk_number) == 114
    assert certificates[0].subject == "test.example"
    assert certificates[0].issuer is None
