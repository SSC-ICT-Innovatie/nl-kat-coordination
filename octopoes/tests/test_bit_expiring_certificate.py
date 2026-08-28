from _datetime import datetime, timedelta

from nibbles.expiring_certificate.expiring_certificate import nibble

from octopoes.models.ooi.certificate import X509Certificate


def test_expiring_cert_simple_success():
    certificate = X509Certificate(
        subject="example.com",
        valid_from="2022-11-15T08:52:57",
        valid_until="2030-11-15T08:52:57",
        serial_number="abc123",
    )

    results = list(nibble(certificate, None))

    assert len(results) == 0


def test_expiring_cert_simple_expired():
    certificate = X509Certificate(
        subject="example.com",
        valid_from="2022-11-15T08:52:57",
        valid_until="2022-11-15T08:52:57",
        serial_number="abc123",
    )

    results = list(nibble(certificate, None))

    assert len(results) == 2


def test_expiring_cert_simple_expires_soon():
    certificate = X509Certificate(
        subject="example.com",
        valid_from="2022-11-15T08:52:57",
        valid_until=str(datetime.now() + timedelta(days=2)),
        serial_number="abc123",
        expires_in=timedelta(days=2),
    )

    results = list(nibble(certificate, None))

    assert len(results) == 2
