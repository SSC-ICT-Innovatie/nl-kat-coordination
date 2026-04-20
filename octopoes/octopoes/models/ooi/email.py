from typing import Literal

from octopoes.models import OOI, Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.persistence import ReferenceField


class EmailAddress(OOI):
    # https://www.rfc-editor.org/rfc/rfc5322#section-3.4.1
    object_type: Literal["EmailAddress"] = "EmailAddress"

    localpart: str = ""
    domain: Reference = ReferenceField(Hostname, max_issue_scan_level=1, max_inherit_scan_level=2)

    _natural_key_attrs = ["localpart", "domain"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        t = reference.tokenized
        localpart = t.localpart
        return f"{localpart}@{t.domain.name} on {t.domain.network.name}"
