from typing import Literal

from octopoes.models import OOI, Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.persistence import ReferenceField


class EmailAddress(OOI):
    """Emailaddress, as per https://www.rfc-editor.org/rfc/rfc5322#section-3.4.1"""

    object_type: Literal["EmailAddress"] = "EmailAddress"

    localpart: str = ""
    # If this address has a scan level, we want to also know some things about the host
    # If this address has no scan level, but its host does, we clearly want to know about this address.
    domain: Reference = ReferenceField(Hostname, max_issue_scan_level=1, max_inherit_scan_level=2)

    _natural_key_attrs = ["localpart", "domain"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        t = reference.tokenized
        localpart = t.localpart
        return f"{localpart}@{t.domain.name} on {t.domain.network.name}"


class EmailAddressInstance(OOI):
    """Bind an EmailAddress to a location that lists it"""

    object_type: Literal["EmailAddressInstance"] = "EmailAddressInstance"

    # We can issue level 1, since we have a vested interest in knowing the security
    # of email-addresses that we found on items with a scan level
    emailaddress: Reference = ReferenceField(EmailAddress, max_issue_scan_level=1)
    # if an address has a scan level, this glue record can have the same
    location: Reference = ReferenceField(OOI, max_inherit_scan_level=4)

    _reverse_relation_names = {"emailaddress": "locations", "location": "emailaddresses"}

    @property
    def natural_key(self) -> str:
        return f"{str(self.location)}|{self.emailaddress.natural_key}"

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        parts = reference.natural_key.split("|")
        domain_name = parts.pop()  # 'example.com'
        domain_network = parts.pop()  # 'internet'
        localpart = parts.pop()  # 'info'
        location = Reference.from_str("|".join(parts))
        return f"{localpart}@{domain_name} on {domain_network} used @ {location.human_readable}"
