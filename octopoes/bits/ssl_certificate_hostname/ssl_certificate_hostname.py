from collections.abc import Iterator

from octopoes.models import OOI
from octopoes.models.ooi.certificate import (
    SubjectAlternativeNameHostname,
    SubjectAlternativeNameQualifier,
    X509Certificate,
)
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import Website


def is_part_of_wildcard(hostname: str, wildcard: str) -> bool:
    # according to rfc2459 wildcard certificates can only be used for subdomains
    wildcard_domain = wildcard[2:].rstrip(".")
    higher_level_domain = ".".join(hostname.split(".")[1:])
    return wildcard_domain == higher_level_domain


def hostname_in_qualifiers(hostname: str, qualifiers: list[str]) -> bool:
    return any(is_part_of_wildcard(hostname, qualifier) for qualifier in qualifiers)


def run(
    input_ooi: X509Certificate, additional_oois: list[Website | SubjectAlternativeNameHostname], config: dict
) -> Iterator[OOI]:
    websites = [website for website in additional_oois if isinstance(website, Website)]
    subject_alternative_name_hostnames = [
        subject_alternative_name.hostname.tokenized.name.rstrip(".")
        for subject_alternative_name in additional_oois
        if isinstance(subject_alternative_name, SubjectAlternativeNameHostname)
    ]

    subject_alternative_name_qualifiers = [
        subject_alternative_name.name.rstrip(".")
        for subject_alternative_name in additional_oois
        if isinstance(subject_alternative_name, SubjectAlternativeNameQualifier)
    ]

    for website in websites:
        hostname = website.hostname.tokenized.name.rstrip(".")

        if hostname in subject_alternative_name_hostnames:
            return

        if hostname_in_qualifiers(hostname, subject_alternative_name_qualifiers):
            return

        ft = KATFindingType(id="KAT-SSL-CERT-HOSTNAME-MISMATCH")
        yield Finding(
            ooi=website.reference,
            finding_type=ft.reference,
            description=f"The hostname {website.hostname} does not match the subject of the certificate",
        )
