from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.dns.zone import ResolvedHostname
from octopoes.models.ooi.network import IPAddress
from octopoes.models.ooi.service import HostnameIPService, IPService


def run(
    ip_address: IPAddress, additional_oois: list[IPService | ResolvedHostname], config: dict[str, Any]
) -> Iterator[OOI]:
    """Link every hostname resolving to this IP address with every service on it.

    The bit instance is keyed on the IPAddress. The framework preselects the
    parameters: IPService and ResolvedHostname objects register themselves on
    this instance only when their outgoing references point at this address,
    so additional_oois is already scoped to it.
    """
    ip_services = [ooi for ooi in additional_oois if isinstance(ooi, IPService)]
    resolved_hostnames = [ooi for ooi in additional_oois if isinstance(ooi, ResolvedHostname)]

    for resolved_hostname in resolved_hostnames:
        for ip_service in ip_services:
            yield HostnameIPService(ip_service=ip_service.reference, hostname=resolved_hostname.hostname)
