import os
from datetime import datetime
from itertools import permutations
from unittest.mock import Mock

import pytest
from jmespath import search
from nibbles.internetnl.nibble import NIBBLE as internetnl
from nibbles.internetnl.nibble import query

from octopoes.core.service import OctopoesService
from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.network import IPAddressV4, IPPort, Network, Protocol
from octopoes.models.ooi.service import IPService, Service
from octopoes.models.ooi.web import HostnameHTTPURL, HTTPHeader, HTTPResource, WebScheme, Website
from octopoes.repositories.ooi_repository import OOIRepository

if os.environ.get("CI") != "1":
    pytest.skip("Needs XTDB multinode container.", allow_module_level=True)

STATIC_IP = ".".join((4 * "1 ").split())
internetnl.enabled = True


def test_internetnl_nibble(xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime):
    xtdb_octopoes_service.nibbler.nibbles = {internetnl.id: internetnl}

    network = Network(name="internet")
    xtdb_octopoes_service.ooi_repository.save(network, valid_time)

    hostname = Hostname(name="example.com", network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)

    web_url = HostnameHTTPURL(
        network=network.reference, netloc=hostname.reference, port=80, path="/", scheme=WebScheme.HTTP
    )
    xtdb_octopoes_service.ooi_repository.save(web_url, valid_time)

    service = Service(name="http")
    xtdb_octopoes_service.ooi_repository.save(service, valid_time)

    ip_address = IPAddressV4(address=STATIC_IP, network=network.reference)
    xtdb_octopoes_service.ooi_repository.save(ip_address, valid_time)

    port = IPPort(port=80, address=ip_address.reference, protocol=Protocol.TCP)
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

    ft = KATFindingType(id="KAT-HTTPS-NOT-AVAILABLE")
    xtdb_octopoes_service.ooi_repository.save(ft, valid_time)

    finding = Finding(
        ooi=website.reference, finding_type=ft.reference, description="HTTP port is open, but HTTPS port is not open"
    )
    xtdb_octopoes_service.ooi_repository.save(finding, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)

    assert xtdb_octopoes_service.ooi_repository.list_oois({Finding}, valid_time).count == 2
    assert xtdb_octopoes_service.ooi_repository.list_oois({KATFindingType}, valid_time).count == 2


def create_port(
    xtdb_ooi_repository: OOIRepository, refs: tuple, ip: str, port: int, valid_time: datetime
) -> IPAddressV4:
    network, hostname, service = refs
    ip_obj = IPAddressV4(address=ip, network=network)
    ipport = IPPort(port=port, address=ip_obj.reference, protocol=Protocol.TCP)
    ip_service = IPService(ip_port=ipport.reference, service=service)
    website = Website(ip_service=ip_service.reference, hostname=hostname)
    ft = KATFindingType(id="KAT-HTTPS-NOT-AVAILABLE")
    finding = Finding(
        ooi=website.reference, finding_type=ft.reference, description="HTTP port is open, but HTTPS port is not open"
    )

    xtdb_ooi_repository.save(ipport, valid_time)
    xtdb_ooi_repository.save(ip_obj, valid_time)
    xtdb_ooi_repository.save(ip_service, valid_time)
    xtdb_ooi_repository.save(website, valid_time)
    xtdb_ooi_repository.save(ft, valid_time)
    xtdb_ooi_repository.save(finding, valid_time)

    xtdb_ooi_repository.commit()

    return ip


def ip_generator():
    for ip in permutations(range(2, 256), 4):
        yield ".".join([str(x) for x in ip])


def test_internetnl_nibble_query(xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime):
    xtdb_octopoes_service.nibbler.nibbles = {internetnl.id: internetnl}

    network = Network(name="internet")
    xtdb_octopoes_service.ooi_repository.save(network, valid_time)

    ip = ip_generator()
    http_service = Service(name="http")

    for i in range(3):
        h = Hostname(name=f"www.x{i}.xyz", network=network.reference)
        xtdb_octopoes_service.ooi_repository.save(h, valid_time)
        http_refs = (network.reference, h.reference, http_service.reference)
        create_port(xtdb_octopoes_service.ooi_repository, http_refs, next(ip), 80, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)

    edn = query([None, None])
    result = xtdb_octopoes_service.ooi_repository.session.client.query(edn)
    assert (
        len(
            {
                xtdb_octopoes_service.ooi_repository.parse_as(Hostname, obj)
                for obj in search(internetnl.signature[0].parser, result)
            }
        )
        == 3
    )
    assert (
        len(
            {
                xtdb_octopoes_service.ooi_repository.parse_as(list[Finding], obj)
                for obj in search(internetnl.signature[1].parser, result)
            }.pop()
        )
        == 3
    )

    edn = query([Reference.from_str("Hostname|internet|www.x1.xyz"), None])
    result = xtdb_octopoes_service.ooi_repository.session.client.query(edn)
    assert (
        len(
            {
                xtdb_octopoes_service.ooi_repository.parse_as(Hostname, obj)
                for obj in search(internetnl.signature[0].parser, result)
            }
        )
        == 1
    )
    assert (
        len(
            {
                xtdb_octopoes_service.ooi_repository.parse_as(list[Finding], obj)
                for obj in search(internetnl.signature[1].parser, result)
            }.pop()
        )
        == 1
    )
