import os
from datetime import datetime
from unittest.mock import Mock

import pytest
from nibbles.missing_mx.nibble import NIBBLE as missing_mx_nibble
from nibbles.runner import NibblesRunner

from octopoes.core.service import OctopoesService
from octopoes.models import ScanLevel
from octopoes.models.ooi.dns.records import NXDOMAIN, DNSMXRecord
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network

if os.environ.get("CI") != "1":
    pytest.skip("Needs XTDB multinode container.", allow_module_level=True)

missing_mx_nibble.signature[0].min_scan_level = ScanLevel.L0


def test_missing_mx_nibble_with_and_without_nx(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    nibbler = NibblesRunner(
        xtdb_octopoes_service.ooi_repository,
        xtdb_octopoes_service.origin_repository,
        xtdb_octopoes_service.scan_profile_repository,
        xtdb_octopoes_service.nibbler.nibble_repository,
    )
    xtdb_octopoes_service.nibbler.disable()
    nibbler.nibbles = {missing_mx_nibble.id: missing_mx_nibble}
    network = Network(name="internet")
    xtdb_octopoes_service.ooi_repository.save(network, valid_time)
    hostname = Hostname(name="test", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_hostname = xtdb_octopoes_service.ooi_repository.get(hostname.reference, valid_time)

    result = nibbler.infer([xtdb_hostname], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert (xtdb_hostname, None, None) in result[hostname][missing_mx_nibble.id]
    assert len(result[hostname][missing_mx_nibble.id][(xtdb_hostname, None, None)]) == 2

    nx_domain = NXDOMAIN(hostname=hostname.reference)
    xtdb_octopoes_service.ooi_repository.save(nx_domain, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_nx = xtdb_octopoes_service.ooi_repository.get(nx_domain.reference, valid_time)
    result = nibbler.infer([xtdb_nx], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert (xtdb_hostname, None, xtdb_nx) in result[nx_domain][missing_mx_nibble.id]
    assert len(result[nx_domain][missing_mx_nibble.id][(xtdb_hostname, None, xtdb_nx)]) == 0


def test_missing_mx_nibble_with_and_without_mx(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    nibbler = NibblesRunner(
        xtdb_octopoes_service.ooi_repository,
        xtdb_octopoes_service.origin_repository,
        xtdb_octopoes_service.scan_profile_repository,
        xtdb_octopoes_service.nibbler.nibble_repository,
    )
    xtdb_octopoes_service.nibbler.disable()
    nibbler.nibbles = {missing_mx_nibble.id: missing_mx_nibble}
    network = Network(name="internet")
    xtdb_octopoes_service.ooi_repository.save(network, valid_time)
    hostname = Hostname(name="test", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_hostname = xtdb_octopoes_service.ooi_repository.get(hostname.reference, valid_time)

    result = nibbler.infer([xtdb_hostname], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert (xtdb_hostname, None, None) in result[hostname][missing_mx_nibble.id]
    assert len(result[hostname][missing_mx_nibble.id][(xtdb_hostname, None, None)]) == 2

    mx_record = DNSMXRecord(hostname=hostname.reference, value="test")
    xtdb_octopoes_service.ooi_repository.save(mx_record, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_mx_record = xtdb_octopoes_service.ooi_repository.get(mx_record.reference, valid_time)
    result = nibbler.infer([xtdb_mx_record], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert (xtdb_hostname, xtdb_mx_record, None) in result[mx_record][missing_mx_nibble.id]
    assert len(result[mx_record][missing_mx_nibble.id][(xtdb_hostname, xtdb_mx_record, None)]) == 0


def test_missing_mx_nibble_non_tld(xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime):
    nibbler = NibblesRunner(
        xtdb_octopoes_service.ooi_repository,
        xtdb_octopoes_service.origin_repository,
        xtdb_octopoes_service.scan_profile_repository,
        xtdb_octopoes_service.nibbler.nibble_repository,
    )
    xtdb_octopoes_service.nibbler.disable()
    nibbler.nibbles = {missing_mx_nibble.id: missing_mx_nibble}
    network = Network(name="internet")
    xtdb_octopoes_service.ooi_repository.save(network, valid_time)
    hostname = Hostname(name="example.example.com", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_hostname = xtdb_octopoes_service.ooi_repository.get(hostname.reference, valid_time)

    result = nibbler.infer([xtdb_hostname], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert (xtdb_hostname, None, None) in result[hostname][missing_mx_nibble.id]
    assert len(result[hostname][missing_mx_nibble.id][(xtdb_hostname, None, None)]) == 0


def test_multiple_objects_queries(xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime):
    xtdb_octopoes_service.nibbler.disable()

    hosts = ["example.com", "mispo.es", "potato.xxx"]
    hostnames = []
    for i in range(3):
        network = Network(name="internet" + str(i))
        xtdb_octopoes_service.ooi_repository.save(network, valid_time)
        hostname = Hostname(name=hosts[i], network=network.reference)
        xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)
        hostnames.append(hostname)

    nx_domain = NXDOMAIN(hostname=hostnames[-1].reference)
    xtdb_octopoes_service.ooi_repository.save(nx_domain, valid_time)

    mx_record = DNSMXRecord(hostname=hostnames[0].reference, value="test")
    xtdb_octopoes_service.ooi_repository.save(mx_record, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)

    result = list(xtdb_octopoes_service.ooi_repository.nibble_query(nx_domain, missing_mx_nibble, valid_time))
    assert list(result[0]) == [hostnames[-1], None, nx_domain]

    result = list(xtdb_octopoes_service.ooi_repository.nibble_query(hostnames[-1], missing_mx_nibble, valid_time))
    assert list(result[0]) == [hostnames[-1], None, nx_domain]

    result = list(xtdb_octopoes_service.ooi_repository.nibble_query(hostnames[0], missing_mx_nibble, valid_time))
    assert list(result[0]) == [hostnames[0], mx_record, None]

    result = list(xtdb_octopoes_service.ooi_repository.nibble_query(mx_record, missing_mx_nibble, valid_time))
    assert list(result[0]) == [hostnames[0], mx_record, None]

    result = list(xtdb_octopoes_service.ooi_repository.nibble_query(hostnames[1], missing_mx_nibble, valid_time))
    assert list(result[0]) == [hostnames[1], None, None]
