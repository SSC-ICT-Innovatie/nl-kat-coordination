import datetime
from collections.abc import Iterator

from octopoes.models import OOI
from octopoes.models.ooi.certificate import X509Certificate
from octopoes.models.ooi.config import Config
from octopoes.models.ooi.findings import Finding, KATFindingType


def nibble(input_ooi: X509Certificate, config: Config | None) -> Iterator[OOI]:
    in_percentage = config.config.get("in_percentage", False) if config and config.config else False
    expiring_very_soon = config.config.get("expiring-very-soon-in-days", 15) if config and config.config else 15
    expiring_soon = config.config.get("expiring-soon-in-days", 30) if config and config.config else 30

    if in_percentage:
        # Calculate percentage thresholds based on certificate validity period
        valid_from = datetime.datetime.fromisoformat(input_ooi.valid_from)
        valid_until = datetime.datetime.fromisoformat(input_ooi.valid_until)
        total_validity = (valid_until - valid_from).days
        threshold_very_soon = datetime.timedelta(days=int(total_validity * expiring_very_soon / 100))
        threshold_soon = datetime.timedelta(days=int(total_validity * expiring_soon / 100))
    else:
        # Use days directly
        threshold_very_soon = datetime.timedelta(days=expiring_very_soon)
        threshold_soon = datetime.timedelta(days=expiring_soon)

    # only applies to OOIs referencing the certificate
    if input_ooi.expired:
        ft = KATFindingType(id="KAT-CERTIFICATE-EXPIRED")
        yield ft
        yield Finding(ooi=input_ooi.reference, finding_type=ft.reference, description="TLS certificate has expired")

    elif input_ooi.expires_in is not None and input_ooi.expires_in < threshold_very_soon:
        ft = KATFindingType(id="KAT-CERTIFICATE-EXPIRING-VERY-SOON")
        yield ft
        yield Finding(
            ooi=input_ooi.reference, finding_type=ft.reference, description="TLS certificate is expiring very soon"
        )
    elif input_ooi.expires_in is not None and input_ooi.expires_in < threshold_soon:
        ft = KATFindingType(id="KAT-CERTIFICATE-EXPIRING-SOON")
        yield ft
        yield Finding(
            ooi=input_ooi.reference, finding_type=ft.reference, description="TLS certificate is expiring soon"
        )
