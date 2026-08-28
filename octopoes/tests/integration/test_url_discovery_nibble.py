import os
from datetime import datetime
from unittest.mock import Mock

import pytest
from nibbles.runner import NibblesRunner
from nibbles.url_discovery.nibble import NIBBLE as url_discovery_nibble

from octopoes.core.service import OctopoesService
from octopoes.models.ooi.dns.zone import Hostname, ResolvedHostname
from octopoes.models.ooi.network import IPAddressV4, IPPort, Network, Protocol

if os.environ.get("CI") != "1":
    pytest.skip("Needs XTDB multinode container.", allow_module_level=True)

STATIC_IP = ".".join((4 * "1 ").split())


def test_url_discovery_nibble_simple_port(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    nibbler = NibblesRunner(
        xtdb_octopoes_service.ooi_repository,
        xtdb_octopoes_service.origin_repository,
        xtdb_octopoes_service.nibbler.scan_profile_repository,
        xtdb_octopoes_service.nibbler.nibble_repository,
    )
    xtdb_octopoes_service.nibbler.disable()
    nibbler.nibbles = {url_discovery_nibble.id: url_discovery_nibble}

    network = Network(name="internet")
    xtdb_octopoes_service.ooi_repository.save(network, valid_time)

    hostname = Hostname(name="example.com", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)

    ip_address = IPAddressV4(address=STATIC_IP, network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(ip_address, valid_time)

    port = IPPort(port=443, address=ip_address.reference, protocol=Protocol.TCP)
    xtdb_octopoes_service.ooi_repository.save(port, valid_time)

    resolved_hostname = ResolvedHostname(address=ip_address.reference, hostname=hostname.reference)
    xtdb_octopoes_service.ooi_repository.save(resolved_hostname, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_port = xtdb_octopoes_service.ooi_repository.get(port.reference, valid_time)
    xtdb_resolved_hostname = xtdb_octopoes_service.ooi_repository.get(resolved_hostname.reference, valid_time)

    result = nibbler.infer([xtdb_port], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert (xtdb_port, xtdb_resolved_hostname) in result[xtdb_port][url_discovery_nibble.id]
    assert len(result[xtdb_port][url_discovery_nibble.id][(xtdb_port, xtdb_resolved_hostname)]) == 1


def test_url_discovery_nibble_simple_resolved_hostname(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    nibbler = NibblesRunner(
        xtdb_octopoes_service.ooi_repository,
        xtdb_octopoes_service.origin_repository,
        xtdb_octopoes_service.nibbler.scan_profile_repository,
        xtdb_octopoes_service.nibbler.nibble_repository,
    )
    xtdb_octopoes_service.nibbler.disable()
    nibbler.nibbles = {url_discovery_nibble.id: url_discovery_nibble}

    network = Network(name="internet")
    xtdb_octopoes_service.ooi_repository.save(network, valid_time)

    hostname = Hostname(name="example.com", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)

    ip_address = IPAddressV4(address=STATIC_IP, network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(ip_address, valid_time)

    port = IPPort(port=443, address=ip_address.reference, protocol=Protocol.TCP)
    xtdb_octopoes_service.ooi_repository.save(port, valid_time)

    resolved_hostname = ResolvedHostname(address=ip_address.reference, hostname=hostname.reference)
    xtdb_octopoes_service.ooi_repository.save(resolved_hostname, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_port = xtdb_octopoes_service.ooi_repository.get(port.reference, valid_time)
    xtdb_resolved_hostname = xtdb_octopoes_service.ooi_repository.get(resolved_hostname.reference, valid_time)

    result = nibbler.infer([xtdb_resolved_hostname], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert (xtdb_port, xtdb_resolved_hostname) in result[xtdb_resolved_hostname][url_discovery_nibble.id]
    assert len(result[xtdb_resolved_hostname][url_discovery_nibble.id][(xtdb_port, xtdb_resolved_hostname)]) == 1


def test_url_discovery_nibble_no_http_port(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    nibbler = NibblesRunner(
        xtdb_octopoes_service.ooi_repository,
        xtdb_octopoes_service.origin_repository,
        xtdb_octopoes_service.nibbler.scan_profile_repository,
        xtdb_octopoes_service.nibbler.nibble_repository,
    )
    xtdb_octopoes_service.nibbler.disable()
    nibbler.nibbles = {url_discovery_nibble.id: url_discovery_nibble}

    network = Network(name="internet")
    xtdb_octopoes_service.ooi_repository.save(network, valid_time)

    hostname = Hostname(name="example.com", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)

    ip_address = IPAddressV4(address=STATIC_IP, network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(ip_address, valid_time)

    port = IPPort(port=1, address=ip_address.reference, protocol=Protocol.TCP)
    xtdb_octopoes_service.ooi_repository.save(port, valid_time)

    resolved_hostname = ResolvedHostname(address=ip_address.reference, hostname=hostname.reference)
    xtdb_octopoes_service.ooi_repository.save(resolved_hostname, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_port = xtdb_octopoes_service.ooi_repository.get(port.reference, valid_time)

    result = nibbler.infer([xtdb_port], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert len(result[xtdb_port][url_discovery_nibble.id]) == 0
