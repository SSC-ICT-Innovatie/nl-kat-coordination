import os
from datetime import datetime
from unittest.mock import Mock

import pytest
from nibbles.runner import NibblesRunner
from nibbles.website_discovery.nibble import NIBBLE as website_discovery_nibble

from octopoes.core.service import OctopoesService
from octopoes.models.ooi.dns.zone import Hostname, ResolvedHostname
from octopoes.models.ooi.network import IPAddressV4, IPPort, Network, Protocol
from octopoes.models.ooi.service import IPService, Service

if os.environ.get("CI") != "1":
    pytest.skip("Needs XTDB multinode container.", allow_module_level=True)

STATIC_IP = ".".join((4 * "1 ").split())


def test_website_discovery_nibble_ip_service(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    nibbler = NibblesRunner(
        xtdb_octopoes_service.ooi_repository,
        xtdb_octopoes_service.origin_repository,
        xtdb_octopoes_service.nibbler.scan_profile_repository,
        xtdb_octopoes_service.nibbler.nibble_repository,
    )
    xtdb_octopoes_service.nibbler.disable()
    nibbler.nibbles = {website_discovery_nibble.id: website_discovery_nibble}

    network = Network(name="internet")
    xtdb_octopoes_service.ooi_repository.save(network, valid_time)

    hostname = Hostname(name="example.com", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)

    ip_address = IPAddressV4(address=STATIC_IP, network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(ip_address, valid_time)

    resolved_hostname = ResolvedHostname(address=ip_address.reference, hostname=hostname.reference)
    xtdb_octopoes_service.ooi_repository.save(resolved_hostname, valid_time)

    port = IPPort(port=443, address=ip_address.reference, protocol=Protocol.TCP)
    xtdb_octopoes_service.ooi_repository.save(port, valid_time)

    service = Service(name="https")
    xtdb_octopoes_service.ooi_repository.save(service, valid_time)

    ip_service = IPService(ip_port=port.reference, service=service.reference)
    xtdb_octopoes_service.ooi_repository.save(ip_service, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_resolved_hostname = xtdb_octopoes_service.ooi_repository.get(resolved_hostname.reference, valid_time)
    xtdb_ip_service = xtdb_octopoes_service.ooi_repository.get(ip_service.reference, valid_time)

    result = nibbler.infer([xtdb_ip_service], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert (xtdb_resolved_hostname, xtdb_ip_service) in result[xtdb_ip_service][website_discovery_nibble.id]
    assert len(result[xtdb_ip_service][website_discovery_nibble.id][(xtdb_resolved_hostname, xtdb_ip_service)]) == 1


def test_website_discovery_nibble_by_resolved_hostname(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    nibbler = NibblesRunner(
        xtdb_octopoes_service.ooi_repository,
        xtdb_octopoes_service.origin_repository,
        xtdb_octopoes_service.nibbler.scan_profile_repository,
        xtdb_octopoes_service.nibbler.nibble_repository,
    )
    xtdb_octopoes_service.nibbler.disable()
    nibbler.nibbles = {website_discovery_nibble.id: website_discovery_nibble}

    network = Network(name="internet")
    xtdb_octopoes_service.ooi_repository.save(network, valid_time)

    hostname = Hostname(name="example.com", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)

    ip_address = IPAddressV4(address=STATIC_IP, network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(ip_address, valid_time)

    resolved_hostname = ResolvedHostname(address=ip_address.reference, hostname=hostname.reference)
    xtdb_octopoes_service.ooi_repository.save(resolved_hostname, valid_time)

    port = IPPort(port=443, address=ip_address.reference, protocol=Protocol.TCP)
    xtdb_octopoes_service.ooi_repository.save(port, valid_time)

    service = Service(name="https")
    xtdb_octopoes_service.ooi_repository.save(service, valid_time)

    ip_service = IPService(ip_port=port.reference, service=service.reference)
    xtdb_octopoes_service.ooi_repository.save(ip_service, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_resolved_hostname = xtdb_octopoes_service.ooi_repository.get(resolved_hostname.reference, valid_time)
    xtdb_ip_service = xtdb_octopoes_service.ooi_repository.get(ip_service.reference, valid_time)

    result = nibbler.infer([xtdb_resolved_hostname], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert (xtdb_resolved_hostname, xtdb_ip_service) in result[xtdb_resolved_hostname][website_discovery_nibble.id]
    assert (
        len(result[xtdb_resolved_hostname][website_discovery_nibble.id][(xtdb_resolved_hostname, xtdb_ip_service)]) == 1
    )
