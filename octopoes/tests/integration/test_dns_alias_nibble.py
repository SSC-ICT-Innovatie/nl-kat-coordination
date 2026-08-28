import os
import string
from datetime import datetime
from unittest.mock import Mock

import pytest
from nibbles.dns_alias_resolving.nibble import NIBBLE as dns_alias_nibble
from nibbles.runner import NibblesRunner

from octopoes.core.service import OctopoesService
from octopoes.models import OOI, Reference
from octopoes.models.ooi.dns.records import DNSCNAMERecord
from octopoes.models.ooi.dns.zone import Hostname, ResolvedHostname
from octopoes.models.ooi.network import IPAddressV4, Network

if os.environ.get("CI") != "1":
    pytest.skip("Needs XTDB multinode container.", allow_module_level=True)

STATIC_IP = ".".join((4 * "1 ").split())


def test_dns_alias_nibble_one_of_each_parameter(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    nibbler = NibblesRunner(
        xtdb_octopoes_service.ooi_repository,
        xtdb_octopoes_service.origin_repository,
        xtdb_octopoes_service.nibbler.scan_profile_repository,
        xtdb_octopoes_service.nibbler.nibble_repository,
    )
    xtdb_octopoes_service.nibbler.disable()

    nibbler.nibbles = {dns_alias_nibble.id: dns_alias_nibble}

    network = Network(name="internet")
    xtdb_octopoes_service.ooi_repository.save(network, valid_time)

    hostname = Hostname(name="example.com", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)
    alias_hostname = Hostname(name="example.org", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(alias_hostname, valid_time)
    ip_address = IPAddressV4(address=STATIC_IP, network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(ip_address, valid_time)

    dns_cname = DNSCNAMERecord(
        hostname=alias_hostname.reference, target_hostname=hostname.reference, value=alias_hostname.name
    )
    xtdb_octopoes_service.ooi_repository.save(dns_cname, valid_time)

    resolved_hostname = ResolvedHostname(hostname=hostname.reference, address=ip_address.reference)
    xtdb_octopoes_service.ooi_repository.save(resolved_hostname, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_dns_cname = xtdb_octopoes_service.ooi_repository.get(dns_cname.reference, valid_time)
    xtdb_resolved_hostname = xtdb_octopoes_service.ooi_repository.get(resolved_hostname.reference, valid_time)

    result = nibbler.infer([xtdb_dns_cname, xtdb_resolved_hostname], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert len(result.keys()) == 3

    assert [
        str(x) for x in result[xtdb_resolved_hostname][dns_alias_nibble.id][(xtdb_dns_cname, xtdb_resolved_hostname)]
    ][0] == "ResolvedHostname|internet|example.org|internet|1.1.1.1"


def test_dns_alias_nibble_no_dns_one_resolved_hostname(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    nibbler = NibblesRunner(
        xtdb_octopoes_service.ooi_repository,
        xtdb_octopoes_service.origin_repository,
        xtdb_octopoes_service.nibbler.scan_profile_repository,
        xtdb_octopoes_service.nibbler.nibble_repository,
    )
    xtdb_octopoes_service.nibbler.disable()

    nibbler.nibbles = {dns_alias_nibble.id: dns_alias_nibble}

    network = Network(name="internet")
    xtdb_octopoes_service.ooi_repository.save(network, valid_time)

    hostname = Hostname(name="example.com", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)
    ip_address = IPAddressV4(address=STATIC_IP, network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(ip_address, valid_time)

    resolved_hostname = ResolvedHostname(hostname=hostname.reference, address=ip_address.reference)
    xtdb_octopoes_service.ooi_repository.save(resolved_hostname, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_resolved_hostname = xtdb_octopoes_service.ooi_repository.get(resolved_hostname.reference, valid_time)

    result = nibbler.infer([xtdb_resolved_hostname], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert len(result.keys()) == 1
    assert not result[xtdb_resolved_hostname][dns_alias_nibble.id]


def test_dns_alias_nibble_one_dns_no_resolved_hostname(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    nibbler = NibblesRunner(
        xtdb_octopoes_service.ooi_repository,
        xtdb_octopoes_service.origin_repository,
        xtdb_octopoes_service.nibbler.scan_profile_repository,
        xtdb_octopoes_service.nibbler.nibble_repository,
    )
    xtdb_octopoes_service.nibbler.disable()

    nibbler.nibbles = {dns_alias_nibble.id: dns_alias_nibble}

    network = Network(name="internet")
    xtdb_octopoes_service.ooi_repository.save(network, valid_time)

    hostname = Hostname(name="example.com", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)
    alias_hostname = Hostname(name="example.org", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(alias_hostname, valid_time)

    dns_cname = DNSCNAMERecord(
        hostname=alias_hostname.reference, target_hostname=hostname.reference, value=alias_hostname.name
    )
    xtdb_octopoes_service.ooi_repository.save(dns_cname, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_dns_cname = xtdb_octopoes_service.ooi_repository.get(dns_cname.reference, valid_time)

    result = nibbler.infer([xtdb_dns_cname], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert len(result.keys()) == 1
    assert not result[xtdb_dns_cname][dns_alias_nibble.id]


def test_dns_alias_nibble_many_dns_one_resolved_hostname(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    nibbler = NibblesRunner(
        xtdb_octopoes_service.ooi_repository,
        xtdb_octopoes_service.origin_repository,
        xtdb_octopoes_service.nibbler.scan_profile_repository,
        xtdb_octopoes_service.nibbler.nibble_repository,
    )
    xtdb_octopoes_service.nibbler.disable()

    nibbler.nibbles = {dns_alias_nibble.id: dns_alias_nibble}

    network = Network(name="internet")
    xtdb_octopoes_service.ooi_repository.save(network, valid_time)

    hostname = Hostname(name="example.com", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)

    ip_address = IPAddressV4(address=STATIC_IP, network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(ip_address, valid_time)

    dns_cnames: list[DNSCNAMERecord] = []
    for prefix in string.ascii_lowercase[:3]:
        alias_hostname = Hostname(name=f"{prefix}.example.com", network=network.reference)
        xtdb_octopoes_service.ooi_repository.save(alias_hostname, valid_time)
        dns_cname = DNSCNAMERecord(
            hostname=alias_hostname.reference, target_hostname=hostname.reference, value=alias_hostname.name
        )
        dns_cnames.append(dns_cname)
        xtdb_octopoes_service.ooi_repository.save(dns_cname, valid_time)

    resolved_hostname = ResolvedHostname(hostname=hostname.reference, address=ip_address.reference)
    xtdb_octopoes_service.ooi_repository.save(resolved_hostname, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)

    xtdb_dns_cnames: list[OOI] = []
    for dns_cname in dns_cnames:
        xtdb_dns_cnames.append(xtdb_octopoes_service.ooi_repository.get(dns_cname.reference, valid_time))

    xtdb_resolved_hostname = xtdb_octopoes_service.ooi_repository.get(resolved_hostname.reference, valid_time)

    result = nibbler.infer(xtdb_dns_cnames + [xtdb_resolved_hostname], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    # We expect 7 results. We made 3 DNSCNAMERecords and 1 ResolvedHostname.
    # Each DNSCNAMERecords should create another ResolvedHostname.
    assert len(result.keys()) == 7, f"Expected 7 results, got {len(result.keys())}"

    # We expect each DNSCNAMERecord to have created a ResolvedHostname.
    assert xtdb_octopoes_service.ooi_repository.get(
        Reference.from_str("ResolvedHostname|internet|a.example.com|internet|1.1.1.1"), valid_time
    )
    assert xtdb_octopoes_service.ooi_repository.get(
        Reference.from_str("ResolvedHostname|internet|b.example.com|internet|1.1.1.1"), valid_time
    )
    assert xtdb_octopoes_service.ooi_repository.get(
        Reference.from_str("ResolvedHostname|internet|c.example.com|internet|1.1.1.1"), valid_time
    )
