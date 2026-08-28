import os
from datetime import datetime
from unittest.mock import Mock

import pytest
from nibbles.check_hsts_header.nibble import NIBBLE as check_hsts_header_nibble
from nibbles.runner import NibblesRunner

from octopoes.core.service import OctopoesService
from octopoes.models.ooi.config import Config
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPPort, Network, Protocol
from octopoes.models.ooi.service import IPService, Service
from octopoes.models.ooi.web import HostnameHTTPURL, HTTPHeader, HTTPResource, WebScheme, Website

if os.environ.get("CI") != "1":
    pytest.skip("Needs XTDB multinode container.", allow_module_level=True)

STATIC_IP = ".".join((4 * "1 ").split())


def test_hsts_nibble_with_and_without_config(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    nibbler = NibblesRunner(
        xtdb_octopoes_service.ooi_repository,
        xtdb_octopoes_service.origin_repository,
        xtdb_octopoes_service.nibbler.scan_profile_repository,
        xtdb_octopoes_service.nibbler.nibble_repository,
    )
    xtdb_octopoes_service.nibbler.disable()
    nibbler.nibbles = {check_hsts_header_nibble.id: check_hsts_header_nibble}

    network = Network(name="internet")
    xtdb_octopoes_service.ooi_repository.save(network, valid_time)

    hostname = Hostname(name="example.com", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)

    web_url = HostnameHTTPURL(
        network=network.reference, netloc=hostname.reference, port=443, path="/", scheme=WebScheme.HTTP
    )
    xtdb_octopoes_service.ooi_repository.save(web_url, valid_time)

    service = Service(name="https")
    xtdb_octopoes_service.ooi_repository.save(service, valid_time)

    ip_address = IPAddressV4(address=STATIC_IP, network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(ip_address, valid_time)

    port = IPPort(port=443, address=ip_address.reference, protocol=Protocol.TCP)
    xtdb_octopoes_service.ooi_repository.save(port, valid_time)

    ip_service = IPService(ip_port=port.reference, service=service.reference)
    xtdb_octopoes_service.ooi_repository.save(ip_service, valid_time)

    website = Website(ip_service=ip_service.reference, hostname=hostname.reference)
    xtdb_octopoes_service.ooi_repository.save(website, valid_time)

    resource = HTTPResource(website=website.reference, web_url=web_url.reference)
    xtdb_octopoes_service.ooi_repository.save(resource, valid_time)

    header = HTTPHeader(
        resource=resource.reference, key="strict-transport-security", value="max-age=21536000; includeSubDomains"
    )
    xtdb_octopoes_service.ooi_repository.save(header, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_header = xtdb_octopoes_service.ooi_repository.get(header.reference, valid_time)

    result = nibbler.infer([xtdb_header], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert (xtdb_header, None) in result[header][check_hsts_header_nibble.id]

    assert len(result[header][check_hsts_header_nibble.id][(xtdb_header, None)]) == 2

    config = Config(ooi=network.reference, config={"max-age": 11536000}, bit_id="check-hsts-header")
    xtdb_octopoes_service.ooi_repository.save(config, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_config = xtdb_octopoes_service.ooi_repository.get(config.reference, valid_time)

    result = nibbler.infer([xtdb_config], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert (xtdb_header, xtdb_config) in result[config][check_hsts_header_nibble.id]

    assert len(result[config][check_hsts_header_nibble.id][(xtdb_header, xtdb_config)]) == 0


def test_hsts_nibble_with_config(xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime):
    nibbler = NibblesRunner(
        xtdb_octopoes_service.ooi_repository,
        xtdb_octopoes_service.origin_repository,
        xtdb_octopoes_service.nibbler.scan_profile_repository,
        xtdb_octopoes_service.nibbler.nibble_repository,
    )
    xtdb_octopoes_service.nibbler.disable()
    nibbler.nibbles = {check_hsts_header_nibble.id: check_hsts_header_nibble}

    network = Network(name="internet")
    xtdb_octopoes_service.ooi_repository.save(network, valid_time)

    hostname = Hostname(name="example.com", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)

    web_url = HostnameHTTPURL(
        network=network.reference, netloc=hostname.reference, port=443, path="/", scheme=WebScheme.HTTP
    )
    xtdb_octopoes_service.ooi_repository.save(web_url, valid_time)

    service = Service(name="https")
    xtdb_octopoes_service.ooi_repository.save(service, valid_time)

    ip_address = IPAddressV4(address=STATIC_IP, network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(ip_address, valid_time)

    port = IPPort(port=443, address=ip_address.reference, protocol=Protocol.TCP)
    xtdb_octopoes_service.ooi_repository.save(port, valid_time)

    ip_service = IPService(ip_port=port.reference, service=service.reference)
    xtdb_octopoes_service.ooi_repository.save(ip_service, valid_time)

    website = Website(ip_service=ip_service.reference, hostname=hostname.reference)
    xtdb_octopoes_service.ooi_repository.save(website, valid_time)

    resource = HTTPResource(website=website.reference, web_url=web_url.reference)
    xtdb_octopoes_service.ooi_repository.save(resource, valid_time)

    header = HTTPHeader(
        resource=resource.reference, key="strict-transport-security", value="max-age=21536000; includeSubDomains"
    )
    xtdb_octopoes_service.ooi_repository.save(header, valid_time)

    config = Config(ooi=network.reference, config={"max-age": 11536000}, bit_id="check-hsts-header")
    xtdb_octopoes_service.ooi_repository.save(config, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_header = xtdb_octopoes_service.ooi_repository.get(header.reference, valid_time)
    xtdb_config = xtdb_octopoes_service.ooi_repository.get(config.reference, valid_time)

    result = nibbler.infer([xtdb_header], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert (xtdb_header, xtdb_config) in result[header][check_hsts_header_nibble.id]

    assert len(result[header][check_hsts_header_nibble.id][(xtdb_header, xtdb_config)]) == 0
