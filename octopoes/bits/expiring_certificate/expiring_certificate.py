import datetime
from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.certificate import TLSCertificateChain, X509CertificateV2
from octopoes.models.ooi.findings import Finding, KATFindingType

# Renewal practice: a certificate should be renewed at one third of its
# lifetime remaining (certbot renews 30 days before Let's Encrypt's 90-day
# certificates). Expiring-soon means that window is half gone: less than
# one sixth of the lifetime remains. No fixed lag: with daily scan
# cadence and the CA/Browser Forum floor of 47-day certificates from
# March 2029, the smallest window any real certificate gets is ~8 days,
# and a shorter (hand-made) certificate expiring unwarned is accurate.
RENEWAL_FRACTION = 6


def _as_utc(value: datetime.datetime) -> datetime.datetime:
    # Storage may hold naive values (hand-declared instances); treat them
    # as UTC rather than crash on the comparison.
    return value if value.tzinfo is not None else value.replace(tzinfo=datetime.UTC)


def run(
    input_ooi: X509CertificateV2, additional_oois: list[TLSCertificateChain], config: dict[str, Any]
) -> Iterator[OOI]:
    """Expiry of a certificate that an endpoint currently presents.

    The finding binds to the certificate — expiry is a property of the
    certificate, not of a presentation — and is only raised while some
    presentation binds the certificate to an IPService or
    HostnameIPService: a certificate known only from the transparency
    logs is inventory, not a live endpoint whose renewal is due.

    Unlike the V1 bit, expiry is computed from the stored validity at
    bit-run time, so the finding follows the calendar instead of being
    frozen at observation time.
    """
    presentations = [
        chain for chain in additional_oois if chain.hostname_ip_service is not None or chain.ip_service is not None
    ]
    if not presentations:
        return

    now = datetime.datetime.now(datetime.UTC)
    valid_until = _as_utc(input_ooi.valid_until)
    valid_from = _as_utc(input_ooi.valid_from)
    fingerprint = input_ooi.fingerprint or input_ooi.subject or "unknown"

    remaining = valid_until - now
    if remaining <= datetime.timedelta(0):
        ft = KATFindingType(id="KAT-CERTIFICATE-EXPIRED")
        yield ft
        yield Finding(
            ooi=input_ooi.reference,
            finding_type=ft.reference,
            description=f"TLS certificate {fingerprint[:16]} expired at {valid_until.isoformat()}.",
        )
        return

    renewal_point = (valid_until - valid_from) / RENEWAL_FRACTION
    if remaining < renewal_point:
        ft = KATFindingType(id="KAT-CERTIFICATE-EXPIRING-SOON")
        yield ft
        yield Finding(
            ooi=input_ooi.reference,
            finding_type=ft.reference,
            description=f"TLS certificate {fingerprint[:16]} is past its renewal point: it expires at"
            f" {valid_until.isoformat()}, in {remaining.days} days. If renewal is automated, the"
            " automation has not replaced it.",
        )
