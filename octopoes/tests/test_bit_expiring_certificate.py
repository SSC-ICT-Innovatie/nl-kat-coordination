from _datetime import datetime, timedelta

from bits.expiring_certificate.expiring_certificate import run

from octopoes.models.ooi.certificate import X509Certificate


def test_expiring_cert_simple_success():
    certificate = X509Certificate(
        subject="example.com",
        valid_from="2022-11-15T08:52:57",
        valid_until="2030-11-15T08:52:57",
        serial_number="abc123",
    )

    results = list(run(certificate, [], {}))

    assert len(results) == 0


def test_expiring_cert_simple_expired():
    certificate = X509Certificate(
        subject="example.com",
        valid_from="2022-11-15T08:52:57",
        valid_until="2022-11-15T08:52:57",
        serial_number="abc123",
    )

    results = list(run(certificate, [], {}))

    assert len(results) == 2


def test_expiring_cert_simple_expires_soon():
    certificate = X509Certificate(
        subject="example.com",
        valid_from="2022-11-15T08:52:57",
        valid_until=str(datetime.now() + timedelta(days=2)),
        serial_number="abc123",
        expires_in=timedelta(days=2),
    )

    results = list(run(certificate, [], {}))

    assert len(results) == 2


def test_expiring_cert_handles_utc_suffix():
    cert = X509Certificate(
        subject="example.com",
        valid_from="2022-11-15T08:52:57",
        valid_until="2022-11-15T08:52:57Z",  # the format that breaks on main
        serial_number="abc123",
    )
    assert cert.expired is True
