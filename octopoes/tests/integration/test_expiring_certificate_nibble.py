import datetime
import os
from unittest.mock import Mock

import pytest
from dateutil.parser import parse
from nibbles.expiring_certificate.nibble import NIBBLE as expiring_certificate_nibble
from nibbles.runner import NibblesRunner

from octopoes.core.service import OctopoesService
from octopoes.models import Reference
from octopoes.models.ooi.certificate import X509Certificate
from octopoes.models.ooi.config import Config
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPPort, Network, Protocol
from octopoes.models.ooi.service import IPService, Service
from octopoes.models.ooi.web import HostnameHTTPURL, WebScheme, Website

if os.environ.get("CI") != "1":
    pytest.skip("Needs XTDB multinode container.", allow_module_level=True)

STATIC_IP = ".".join((4 * "1 ").split())


def test_expiring_certificate_expired(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    nibbler = NibblesRunner(
        xtdb_octopoes_service.ooi_repository,
        xtdb_octopoes_service.origin_repository,
        xtdb_octopoes_service.nibbler.scan_profile_repository,
        xtdb_octopoes_service.nibbler.nibble_repository,
    )
    xtdb_octopoes_service.nibbler.disable()
    nibbler.nibbles = {expiring_certificate_nibble.id: expiring_certificate_nibble}

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

    expired_date = datetime.datetime.now() - datetime.timedelta(weeks=2)
    certificate = X509Certificate(
        valid_from=datetime.datetime.isoformat(expired_date),
        valid_until=datetime.datetime.isoformat(expired_date),
        serial_number="XXX",
    )
    xtdb_octopoes_service.ooi_repository.save(certificate, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_certificate = xtdb_octopoes_service.ooi_repository.get(certificate.reference, valid_time)

    result = nibbler.infer([xtdb_certificate], valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert (xtdb_certificate, None) in result[certificate][expiring_certificate_nibble.id]

    result_set = result[certificate][expiring_certificate_nibble.id][(xtdb_certificate, None)]
    references = [Reference.from_str(ooi) for ooi in list(result_set)]

    assert len(references) == 2
    assert Reference.from_str("KATFindingType|KAT-CERTIFICATE-EXPIRED") in references


def test_expiring_certificate_expiring_soon(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    nibbler = NibblesRunner(
        xtdb_octopoes_service.ooi_repository,
        xtdb_octopoes_service.origin_repository,
        xtdb_octopoes_service.nibbler.scan_profile_repository,
        xtdb_octopoes_service.nibbler.nibble_repository,
    )
    xtdb_octopoes_service.nibbler.disable()
    nibbler.nibbles = {expiring_certificate_nibble.id: expiring_certificate_nibble}

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

    expired_date = datetime.datetime.now() + datetime.timedelta(days=14)
    valid_until = datetime.datetime.isoformat(expired_date)
    certificate = X509Certificate(
        valid_from=valid_until,
        valid_until=valid_until,
        issuer="XXX",
        serial_number="XXX",
        expires_in=parse(valid_until).astimezone(datetime.timezone.utc) - datetime.datetime.now(datetime.timezone.utc),
    )
    xtdb_octopoes_service.ooi_repository.save(certificate, valid_time)

    website = Website(ip_service=ip_service.reference, hostname=hostname.reference, certificate=certificate.reference)
    xtdb_octopoes_service.ooi_repository.save(website, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_certificate = xtdb_octopoes_service.ooi_repository.get(certificate.reference, valid_time)

    result = nibbler.infer([xtdb_certificate], valid_time)

    result_set = result[certificate][expiring_certificate_nibble.id][(xtdb_certificate, None)]
    references = [Reference.from_str(ooi) for ooi in list(result_set)]

    assert len(references) == 2
    assert Reference.from_str("KATFindingType|KAT-CERTIFICATE-EXPIRING-VERY-SOON") in references

    # we config the nibble to yield soon expiring findings now instead of very soon
    config = Config(
        ooi=network.reference,
        config={"expiring-very-soon-in-days": 2, "expiring-soon-in-days": 15},
        bit_id="expiring-certificate",
    )
    xtdb_octopoes_service.ooi_repository.save(config, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_config = xtdb_octopoes_service.ooi_repository.get(config.reference, valid_time)

    result = nibbler.infer([xtdb_certificate], valid_time)

    result_set = result[certificate][expiring_certificate_nibble.id][(xtdb_certificate, xtdb_config)]
    references = [Reference.from_str(ooi) for ooi in list(result_set)]

    assert len(references) == 2
    assert Reference.from_str("KATFindingType|KAT-CERTIFICATE-EXPIRING-SOON") in references

    # we config the nibble to only yield findings when certs expire in 2 days
    config = Config(
        ooi=network.reference,
        config={"expiring-very-soon-in-days": 2, "expiring-soon-in-days": 2},
        bit_id="expiring-certificate",
    )
    xtdb_octopoes_service.ooi_repository.save(config, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_config = xtdb_octopoes_service.ooi_repository.get(config.reference, valid_time)

    # so the finding should disappear
    result = nibbler.infer([xtdb_certificate], valid_time)
    assert len(result[certificate][expiring_certificate_nibble.id][(xtdb_certificate, xtdb_config)]) == 0

    # now we config the nibble to yield findings when certs expire in 20 days
    config = Config(
        ooi=network.reference,
        config={"expiring-very-soon-in-days": 20, "expiring-soon-in-days": 20},
        bit_id="expiring-certificate",
    )
    xtdb_octopoes_service.ooi_repository.save(config, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)
    xtdb_config = xtdb_octopoes_service.ooi_repository.get(config.reference, valid_time)

    # so the finding should appear again
    result = nibbler.infer([xtdb_certificate], valid_time)
    assert len(result[certificate][expiring_certificate_nibble.id][(xtdb_certificate, xtdb_config)]) == 2

    # test if same results are returned when the nibble is run from the config
    result = nibbler.infer([xtdb_certificate], valid_time)
    assert len(result[certificate][expiring_certificate_nibble.id][(xtdb_certificate, xtdb_config)]) == 2
