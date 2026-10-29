from collections.abc import Iterator
from typing import Any
from urllib.parse import urlsplit

from pydantic import ValidationError

from octopoes.models import OOI
from octopoes.models.ooi.dns.records import CAATAGS, DNSCAAAccountURI, DNSCAARecord
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.email import EmailAddress, EmailAddressInstance
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import URL


def parse_caa_parameters(value: str) -> dict[str, list[str]]:
    parameters: dict[str, list[str]] = {}

    for part in value.split(";")[1:]:
        key, separator, parameter_value = part.strip().partition("=")

        if separator:
            parameters.setdefault(key.strip().lower(), []).append(parameter_value.strip())

    return parameters


def run(record: DNSCAARecord, additional_oois: list[OOI], config: dict[str, Any]) -> Iterator[OOI]:
    findings: list[tuple[str, str]] = []

    if record.tag == CAATAGS.IODEF:
        value = record.value.strip()

        try:
            parsed = urlsplit(value)
            scheme = parsed.scheme.lower()

            if scheme == "mailto":
                address = parsed.path

                if not address or address.count("@") != 1:
                    findings.append(("KAT-CAA-IODEF", "Malformed mailto URI in CAA iodef record."))
                else:
                    localpart, hostname = address.rsplit("@", 1)

                    if not localpart or not hostname:
                        findings.append(("KAT-CAA-IODEF", "Missing localpart or hostname in CAA iodef mailto URI."))
                    else:
                        hostnameobj = Hostname(name=hostname.lower(), network=record.hostname.network)
                        emailaddress = EmailAddress(localpart=localpart, hostname=hostnameobj.reference)

                        yield hostnameobj
                        yield emailaddress
                        yield EmailAddressInstance(emailaddress=emailaddress.reference, location=record.reference)

            elif scheme in ("http", "https"):
                if not parsed.netloc or not parsed.hostname:
                    findings.append(("KAT-CAA-IODEF", "Malformed HTTP(S) URI in CAA iodef record."))
                else:
                    yield URL(network=record.hostname.network, raw=value)

            else:
                findings.append(("KAT-CAA-IODEF", f"Unsupported URI scheme '{scheme}' in CAA iodef record."))

        except (ValueError, ValidationError) as exc:
            findings.append(("KAT-CAA-IODEF", f"Invalid iodef URI in CAA record: {exc}"))

    elif record.tag in (CAATAGS.ISSUE, CAATAGS.ISSUEWILD):
        parameters = parse_caa_parameters(record.value)
        account_uris = parameters.get("accounturi", [])

        if len(account_uris) > 1:
            findings.append(("KAT-CAA-ACCOUNTURI", "Multiple accounturi parameters in a single CAA record."))

        elif len(account_uris) == 1:
            uri = account_uris[0]

            if not uri:
                findings.append(("KAT-CAA-ACCOUNTURI", "Empty accounturi parameter in a CAA record."))
            else:
                try:
                    account_uri_object = DNSCAAAccountURI(uri=uri)
                    yield account_uri_object

                    yield record.model_copy(update={"accounturi": account_uri_object.reference})

                except ValidationError as exc:
                    findings.append(("KAT-CAA-ACCOUNTURI", f"Invalid accounturi parameter: {exc}"))

    for finding_type_id, description in findings:
        ft = KATFindingType(finding_type_id)
        yield ft

        yield Finding(proof=record.value, finding_type=ft.reference, ooi=record.reference, description=description)
