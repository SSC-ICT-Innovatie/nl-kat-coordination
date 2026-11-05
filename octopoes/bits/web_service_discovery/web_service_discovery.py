from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI, PrimaryKeyToken, Reference
from octopoes.models.ooi.network import IPAddress
from octopoes.models.ooi.service import HostnameIPService, IPService
from octopoes.models.ooi.web import Website

WEB_SERVICES = ("http", "https")


def _canonical_website(ip_service: IPService, hostname_name: str, network_name: str) -> Website:
    """The Website for the (IPService, hostname) pair, built from tokens.

    The natural key is the concatenation of the two roots' keys, so the
    canonical object is built from the embedded tokens — never from a
    HostnameIPService reference, which would embed the hostname twice."""
    tokenized = ip_service.reference.tokenized
    ip_port = tokenized.ip_port
    return Website(
        ip_service=Reference.from_str(
            f"IPService|{ip_port.address.network.name}|{ip_port.address.address}"
            f"|{ip_port.protocol}|{ip_port.port}|{tokenized.service.name}"
        ),
        hostname=Reference.from_str(f"Hostname|{network_name}|{hostname_name}"),
    )


def run(
    input_ooi: IPAddress, additional_oois: list[IPService | HostnameIPService], config: dict[str, Any]
) -> Iterator[OOI]:
    """Frame web-served endpoints on this address as websites.

    Two cases, both derived from the same two roots (IPService, Hostname):

    - a HostnameIPService for http/https binds a name to a web service:
      the Website pairs the same roots (name case);
    - a bare IPService for http/https with *no* name binding serves the
      web without a hostname: the Website pairs it with the IP-as-hostname
      placeholder (null-SNI case). Not supporting it would be a regression:
      the header-analysis ecosystem reads websites off IP addresses, and
      the pre-migration normalizers wrote exactly this object.

    A non-web HostnameIPService (imaps, smtp, ...) yields nothing: it binds
    a name to a service, it does not make the service a website."""
    ip_services = {ooi.reference: ooi for ooi in additional_oois if isinstance(ooi, IPService)}
    hostnames_by_service: dict[str, list[PrimaryKeyToken]] = {}
    for ooi in additional_oois:
        if isinstance(ooi, HostnameIPService):
            tokenized = ooi.reference.tokenized
            service_token = tokenized.ip_service
            service_key = (
                f"{service_token.ip_port.address.network.name}|{service_token.ip_port.address.address}"
                f"|{service_token.ip_port.protocol}|{service_token.ip_port.port}|{service_token.service.name}"
            )
            hostnames_by_service.setdefault(service_key, []).append(tokenized.hostname)

    network_name = input_ooi.reference.tokenized.network.name

    for ip_service in ip_services.values():
        service_name = ip_service.reference.tokenized.service.name.lower()
        if service_name not in WEB_SERVICES:
            continue

        tokenized = ip_service.reference.tokenized
        ip_port = tokenized.ip_port
        service_key = (
            f"{ip_port.address.network.name}|{ip_port.address.address}"
            f"|{ip_port.protocol}|{ip_port.port}|{tokenized.service.name}"
        )
        hostname_tokens = hostnames_by_service.get(service_key, [])
        if hostname_tokens:
            # Name-bound case: one Website per name binding.
            for hostname_token in hostname_tokens:
                yield _canonical_website(ip_service, hostname_token.name, hostname_token.network.name)
        else:
            # Null-SNI case: the IP-as-hostname placeholder.
            yield _canonical_website(ip_service, input_ooi.reference.tokenized.address, network_name)
