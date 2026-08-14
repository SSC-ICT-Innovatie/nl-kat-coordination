from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.dns.records import DNSSOARecord
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.email import EmailAddress


def _split_soa_rname(rname: str) -> list[str]:
    parts = []
    buf = []
    escaped = False

    for ch in rname.rstrip("."):
        if escaped:
            buf.append(ch)
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == ".":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)

    parts.append("".join(buf))
    return parts


def soa_rname_to_email(rname: str) -> str:
    parts = _split_soa_rname(rname.lower())
    if len(parts) < 2:
        return ""

    localpart = parts[0]
    domain = ".".join(parts[1:])
    return f"{localpart}@{domain}"


def run(soa_record: DNSSOARecord, additional_oois: None, config: dict[str, Any]) -> Iterator[OOI]:
    if soa_record.rname:
        # extract email from SOA rname
        email = soa_rname_to_email(str(soa_record.rname))

        if email and "@" in email:
            localpart, domain = email.split("@", 1)

            domain_ooi = Hostname(network=soa_record.soa_hostname, name=domain)
            yield domain_ooi
            emailaddress = EmailAddress(
                network=soa_record.soa_hostname, localpart=localpart, domain=domain_ooi.reference
            )
            yield emailaddress
            soa_record.email = emailaddress.reference
            yield soa_record
            # We dont yield an EmailAddressInstance, as the soar_record itself already contains
            # a reference to the address.
