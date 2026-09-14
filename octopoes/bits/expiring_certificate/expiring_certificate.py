import datetime
from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.certificate import X509Certificate
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import Website

THRESHOLD = datetime.timedelta(weeks=2)


def run(input_ooi: X509Certificate, additional_oois: list[Website], config: dict[str, Any]) -> Iterator[OOI]:
    # only applies to OOIs referencing the certificate
    if input_ooi.expired:
        ft = KATFindingType(id="KAT-CERTIFICATE-EXPIRED")
        yield ft
        yield Finding(ooi=input_ooi.reference, finding_type=ft.reference, description="TLS certificate has expired")

    elif input_ooi.expires_in < THRESHOLD:
        ft = KATFindingType(id="KAT-CERTIFICATE-EXPIRING-SOON")
        yield ft
        yield Finding(
            ooi=input_ooi.reference, finding_type=ft.reference, description="TLS certificate is expiring soon"
        )
