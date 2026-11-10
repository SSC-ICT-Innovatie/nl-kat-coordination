import datetime
from datetime import UTC, timedelta

from bits.expiring_certificate.expiring_certificate import run

from octopoes.models.ooi.certificate import TLSCertificateChain, X509CertificateV2
from octopoes.models.ooi.findings import Finding


def _certificate(**overrides) -> X509CertificateV2:
    now = datetime.datetime.now(datetime.UTC)
    fields = {
        "fingerprint": "a" * 64,
        "subject": "CN=example.com",
        "valid_from": now - timedelta(days=75),
        "valid_until": now + timedelta(days=15),
    }
    fields.update(overrides)
    return X509CertificateV2(**fields)


def _chain(certificate: X509CertificateV2, **endpoint) -> TLSCertificateChain:
    return TLSCertificateChain(
        presentation_hash="abc123",
        presented_certificates=[certificate.reference],
        **(
            endpoint
            or {"hostname_ip_service": "HostnameIPService|internet|192.0.2.10|tcp|443|https|internet|example.com"}
        ),
    )


def _findings(results) -> dict[str, Finding]:
    return {str(f.finding_type): f for f in results if isinstance(f, Finding)}


def test_expiring_certificate_fires_on_the_certificate():
    # A 90-day lifetime: the renewal point is one third remaining
    # (certbot practice); the bit warns when that window is half gone —
    # one sixth remaining, 15 days for a 90-day certificate.
    certificate = _certificate()
    results = list(run(certificate, [_chain(certificate)], {}))

    finding = _findings(results)["KATFindingType|KAT-CERTIFICATE-EXPIRING-SOON"]
    # About the certificate, not the chain.
    assert finding.ooi == certificate.reference
    assert "renewal point" in finding.description


def test_expired_certificate_fires_on_the_certificate():
    now = datetime.datetime.now(datetime.UTC)
    certificate = _certificate(valid_from=now - timedelta(days=200), valid_until=now - timedelta(days=1))
    results = list(run(certificate, [_chain(certificate)], {}))

    finding = _findings(results)["KATFindingType|KAT-CERTIFICATE-EXPIRED"]
    assert finding.ooi == certificate.reference
    assert "expired at" in finding.description


def test_certificate_with_one_third_remaining_does_not_fire():
    # Exactly at the renewal point (1/3 of 90 days = 30 days remaining)
    # nothing fires yet: the bit warns when the window is half gone.
    now = datetime.datetime.now(datetime.UTC)
    certificate = _certificate(valid_from=now - timedelta(days=60), valid_until=now + timedelta(days=30))

    assert list(run(certificate, [_chain(certificate)], {})) == []


def test_certificate_before_renewal_point_does_not_fire():
    now = datetime.datetime.now(datetime.UTC)
    certificate = _certificate(valid_from=now - timedelta(days=50), valid_until=now + timedelta(days=40))

    assert list(run(certificate, [_chain(certificate)], {})) == []


def test_certificate_without_presentation_is_not_assessed():
    # Known only from the transparency logs: no endpoint binds it, so no
    # renewal is due and nothing fires.
    certificate = _certificate(valid_until=datetime.datetime.now(datetime.UTC) - timedelta(days=1))

    assert list(run(certificate, [], {})) == []


def test_null_sni_presentation_counts_as_bound():
    # A chain keyed on the bare IPService binds the certificate to an
    # endpoint just as an SNI-qualified chain does.
    certificate = _certificate(valid_until=datetime.datetime.now(datetime.UTC) - timedelta(days=1))
    chain = _chain(certificate, ip_service="IPService|internet|192.0.2.10|tcp|443|https")

    finding = _findings(list(run(certificate, [chain], {})))["KATFindingType|KAT-CERTIFICATE-EXPIRED"]
    assert finding.ooi == certificate.reference


def test_naive_stored_validity_is_treated_as_utc():
    # Hand-declared instances may carry naive datetimes (the fixtures do);
    # the comparison must not crash on them.
    now = datetime.datetime.now(UTC).replace(tzinfo=None)
    certificate = _certificate(valid_from=now - timedelta(days=200), valid_until=now - timedelta(days=1))
    certificate = X509CertificateV2(
        fingerprint=certificate.fingerprint,
        subject=certificate.subject,
        valid_from=certificate.valid_from.replace(tzinfo=None),
        valid_until=certificate.valid_until.replace(tzinfo=None),
    )

    assert _findings(list(run(certificate, [_chain(certificate)], {})))
