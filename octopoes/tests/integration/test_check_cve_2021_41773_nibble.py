import os
from datetime import datetime
from unittest.mock import Mock

import pytest
from nibbles.check_cve_2021_41773.nibble import NIBBLE as check_cve_2021_41773_nibble
from nibbles.runner import NibblesRunner

from octopoes.core.service import OctopoesService
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPPort, Network, Protocol
from octopoes.models.ooi.service import IPService, Service
from octopoes.models.ooi.web import HostnameHTTPURL, HTTPHeader, HTTPResource, WebScheme, Website

if os.environ.get("CI") != "1":
    pytest.skip("Needs XTDB multinode container.", allow_module_level=True)

STATIC_IP = ".".join((4 * "1 ").split())


def test_check_cve_2021_41773_nibble(xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime):
    nibbler = NibblesRunner(
        xtdb_octopoes_service.ooi_repository,
        xtdb_octopoes_service.origin_repository,
        xtdb_octopoes_service.nibbler.scan_profile_repository,
        xtdb_octopoes_service.nibbler.nibble_repository,
    )
    xtdb_octopoes_service.nibbler.disable()
    nibbler.nibbles = {check_cve_2021_41773_nibble.id: check_cve_2021_41773_nibble}

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

    header_good = HTTPHeader(resource=resource.reference, key="Server", value="Apache/2.4.48")
    xtdb_octopoes_service.ooi_repository.save(header_good, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_header = xtdb_octopoes_service.ooi_repository.get(header_good.reference, valid_time)

    result = nibbler.infer([xtdb_header], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert (xtdb_header,) in result[header_good][check_cve_2021_41773_nibble.id]

    assert len(result[header_good][check_cve_2021_41773_nibble.id][(xtdb_header,)]) == 0

    header_good = HTTPHeader(resource=resource.reference, key="Server", value="Apache/2.4.49")
    xtdb_octopoes_service.ooi_repository.save(header_good, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_header = xtdb_octopoes_service.ooi_repository.get(header_good.reference, valid_time)

    result = nibbler.infer([xtdb_header], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert (xtdb_header,) in result[header_good][check_cve_2021_41773_nibble.id]

    assert len(result[header_good][check_cve_2021_41773_nibble.id][(xtdb_header,)]) == 2
