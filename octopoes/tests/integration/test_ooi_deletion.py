import os
import time
import uuid
from datetime import datetime
from ipaddress import ip_address
from unittest.mock import Mock

import pytest

from octopoes.api.models import Affirmation, Declaration, Observation
from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.core.service import OctopoesService
from octopoes.events.events import OOIDBEvent, OriginDBEvent
from octopoes.models import OOI, ScanLevel
from octopoes.models.ooi.dns.records import NXDOMAIN, DNSARecord
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.monitoring import Application
from octopoes.models.ooi.network import IPAddressV4, Network
from octopoes.models.ooi.software import Software, SoftwareInstance
from octopoes.models.origin import Origin, OriginType

if os.environ.get("CI") != "1":
    pytest.skip("Needs XTDB multinode container.", allow_module_level=True)


def printer(arg1, arg2):
    print(arg1)
    for i, k in enumerate(arg2):
        print(f">>{i}: {k}<<")
    print()


@pytest.mark.xfail(reason="Issue #2083")
def test_hostname_nxd_ooi(octopoes_api_connector: OctopoesAPIConnector, valid_time: datetime):
    network = Network(name="internet")
    octopoes_api_connector.save_declaration(Declaration(ooi=network, valid_time=valid_time))
    url = "mispo.es"
    hostname = Hostname(network=network.reference, name=url)
    octopoes_api_connector.save_declaration(Declaration(ooi=hostname, valid_time=valid_time))

    original_size = len(octopoes_api_connector.list_origins(task_id={}, valid_time=valid_time))
    assert original_size >= 2
    octopoes_api_connector.recalculate_bits()
    bits_size = len(octopoes_api_connector.list_origins(task_id={}, valid_time=valid_time))
    assert bits_size >= original_size

    nxd = NXDOMAIN(hostname=hostname.reference)
    octopoes_api_connector.save_observation(
        Observation(
            method="normalizer_id", source=hostname.reference, task_id=uuid.uuid4(), valid_time=valid_time, result=[nxd]
        )
    )
    octopoes_api_connector.recalculate_bits()

    octopoes_api_connector.delete(network.reference, valid_time=valid_time)
    octopoes_api_connector.delete(hostname.reference, valid_time=valid_time)

    # This sleep is here because otherwise on some systems this test will fail
    # Delete when issue #2083 is resolved...
    time.sleep(2)
    assert len(octopoes_api_connector.list_origins(task_id={}, valid_time=valid_time)) < bits_size

    octopoes_api_connector.recalculate_bits()

    assert len(octopoes_api_connector.list_origins(task_id={}, valid_time=valid_time)) < original_size


def test_events_created_through_crud(xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime):
    network = Network(name="internet")

    origin = Origin(
        origin_type=OriginType.DECLARATION,
        method="",
        source=network.reference,
        result=[network.reference],
        task_id=uuid.uuid4(),
    )
    xtdb_octopoes_service.save_origin(origin, [network], valid_time)
    xtdb_octopoes_service.commit()

    assert len(event_manager.queue) == 2

    call1 = event_manager.queue[0]
    call2 = event_manager.queue[1]

    assert isinstance(call1, OOIDBEvent)
    assert isinstance(call2, OriginDBEvent)

    assert call1.old_data is None
    assert call1.new_data == network
    assert call1.operation_type.value == "create"

    assert call2.old_data is None
    assert call2.new_data == origin
    assert call2.operation_type.value == "create"

    xtdb_octopoes_service.ooi_repository.delete_if_exists(network.reference, valid_time)
    xtdb_octopoes_service.commit()

    assert len(event_manager.queue) == 3  # Origin will be deleted by the worker due to the OOI delete event
    call3 = event_manager.queue[2]
    assert isinstance(call3, OOIDBEvent)
    assert call3.operation_type.value == "delete"


def test_events_created_in_worker_during_handling(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    network = Network(name="internet")

    origin = Origin(
        origin_type=OriginType.DECLARATION,
        method="",
        source=network.reference,
        result=[network.reference],
        task_id=uuid.uuid4(),
    )
    xtdb_octopoes_service.save_origin(origin, [network], valid_time)
    xtdb_octopoes_service.commit()
    xtdb_octopoes_service.ooi_repository.delete_if_exists(network.reference, valid_time)
    xtdb_octopoes_service.commit()

    assert len(event_manager.queue) == 3
    event = event_manager.queue[2]  # OOIDelete event

    assert isinstance(event, OOIDBEvent)
    assert event.operation_type.value == "delete"

    for event in event_manager.queue:
        xtdb_octopoes_service.process_event(event)
    xtdb_octopoes_service.commit()

    assert len(event_manager.queue) == 5  # Handling OOI delete event triggers Origin delete event

    event = event_manager.queue[4]  # OOIDelete event

    assert isinstance(event, OriginDBEvent)
    assert event.operation_type.value == "delete"


def test_events_deletion_after_bits(xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime):
    network = Network(name="internet")

    origin = Origin(
        origin_type=OriginType.DECLARATION,
        method="manual",
        source=network.reference,
        result=[network.reference],
        task_id=uuid.uuid4(),
    )

    url = "mispo.es"
    hostname = Hostname(network=network.reference, name=url)

    xtdb_octopoes_service.save_origin(origin, [network], valid_time)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)
    print(1)
    print(f"PROCESSED {event_manager.complete_process_events(xtdb_octopoes_service)}")
    printer("OOIS", xtdb_octopoes_service.ooi_repository.list_oois({OOI}, valid_time).items)
    printer("ORIGINS", xtdb_octopoes_service.origin_repository.list_origins(valid_time))
    printer("EVENTS", event_manager.queue)

    xtdb_octopoes_service.recalculate_bits()

    print(2)
    print(f"PROCESSED {event_manager.complete_process_events(xtdb_octopoes_service)}")
    printer("OOIS", xtdb_octopoes_service.ooi_repository.list_oois({OOI}, valid_time).items)
    printer("ORIGINS", xtdb_octopoes_service.origin_repository.list_origins(valid_time))
    printer("EVENTS", event_manager.queue)

    xtdb_octopoes_service.ooi_repository.delete_if_exists(network.reference, valid_time)
    xtdb_octopoes_service.ooi_repository.delete_if_exists(hostname.reference, valid_time)

    print(3)
    print(f"PROCESSED {event_manager.complete_process_events(xtdb_octopoes_service)}")
    printer("OOIS", xtdb_octopoes_service.ooi_repository.list_oois({OOI}, valid_time).items)
    printer("ORIGINS", xtdb_octopoes_service.origin_repository.list_origins(valid_time))
    printer("EVENTS", event_manager.queue)

    print(f"TOTAL PROCESSED {event_manager.processed}")


def test_deletion_events_after_nxdomain(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    xtdb_octopoes_service.nibbler.nibbles["missing-spf"].signature[0].min_scan_level = ScanLevel.L0

    network = Network(name="internet")

    origin = Origin(
        origin_type=OriginType.DECLARATION,
        method="manual",
        source=network.reference,
        result=[network.reference],
        task_id=uuid.uuid4(),
    )

    url = "mispo.es"
    hostname = Hostname(network=network.reference, name=url)

    xtdb_octopoes_service.save_origin(origin, [network], valid_time)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)

    finding_types = [
        KATFindingType(id="KAT-NO-SPF"),
        KATFindingType(id="KAT-NO-DMARC"),
        KATFindingType(id="KAT-NO-DKIM"),
    ]

    findings = [Finding(finding_type=ft.reference, ooi=hostname.reference) for ft in finding_types]

    finding_origin = Origin(
        origin_type=OriginType.OBSERVATION,
        method="",
        source=network.reference,
        result=[finding.reference for finding in findings],
        task_id=uuid.uuid4(),
    )

    for finding in findings:
        xtdb_octopoes_service.ooi_repository.save(finding, valid_time)
    xtdb_octopoes_service.save_origin(finding_origin, findings, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)

    xtdb_octopoes_service.recalculate_bits()

    event_manager.complete_process_events(xtdb_octopoes_service)

    assert len(list(filter(lambda x: x.operation_type.value == "delete", event_manager.queue))) == 0
    assert xtdb_octopoes_service.ooi_repository.list_oois({OOI}, valid_time).count == 12

    nxd = NXDOMAIN(hostname=hostname.reference)
    xtdb_octopoes_service.ooi_repository.save(nxd, valid_time)

    nxd_origin = Origin(
        origin_type=OriginType.OBSERVATION,
        method="",
        source=network.reference,
        result=[nxd.reference],
        task_id=uuid.uuid4(),
    )
    xtdb_octopoes_service.save_origin(nxd_origin, [nxd], valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)

    xtdb_octopoes_service.recalculate_bits()

    event_manager.complete_process_events(xtdb_octopoes_service)

    assert len(list(filter(lambda x: x.operation_type.value == "delete", event_manager.queue))) >= 3
    assert xtdb_octopoes_service.ooi_repository.list_oois({OOI}, valid_time).count == 9


@pytest.mark.xfail(reason="Wappalyzer works on wrong input objects (to be addressed)")
def test_deletion_events_after_nxdomain_with_wappalyzer_findings_included(
    xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime
):
    network = Network(name="internet")

    origin = Origin(
        origin_type=OriginType.DECLARATION,
        method="",
        source=network.reference,
        result=[network.reference],
        task_id=uuid.uuid4(),
    )

    url = "mispo.es"
    hostname = Hostname(network=network.reference, name=url)

    xtdb_octopoes_service.save_origin(origin, [network], valid_time)
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)

    software_oois = [
        Software(name="Bootstrap", version="3.3.7", cpe="cpe:/a:getbootstrap:bootstrap"),
        Software(name="Nginx", version="1.18.0", cpe="cpe:/a:nginx:nginx"),
        Software(name="cdnjs"),
        Software(name="jQuery Migrate", version="1.0.0"),
        Software(name="jQuery", version="3.6.0", cpe="cpe:/a:jquery:jquery"),
    ]
    instances = [SoftwareInstance(ooi=hostname.reference, software=software.reference) for software in software_oois]

    software_origin = Origin(
        origin_type=OriginType.OBSERVATION,
        method="",
        source=network.reference,
        result=[x.reference for x in (software_oois + instances)],
        task_id=uuid.uuid4(),
    )

    for software, instance in zip(software_oois, instances):
        xtdb_octopoes_service.ooi_repository.save(software, valid_time)
        xtdb_octopoes_service.ooi_repository.save(instance, valid_time)
    xtdb_octopoes_service.save_origin(software_origin, software_oois + instances, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)

    xtdb_octopoes_service.recalculate_bits()

    finding_types = [
        KATFindingType(id="KAT-NO-SPF"),
        KATFindingType(id="KAT-NO-DMARC"),
        KATFindingType(id="KAT-NO-DKIM"),
    ]

    findings = [Finding(finding_type=ft.reference, ooi=hostname.reference) for ft in finding_types]

    finding_origin = Origin(
        origin_type=OriginType.OBSERVATION,
        method="",
        source=network.reference,
        result=[finding.reference for finding in findings],
        task_id=uuid.uuid4(),
    )

    for finding in findings:
        xtdb_octopoes_service.ooi_repository.save(finding, valid_time)
    xtdb_octopoes_service.save_origin(finding_origin, findings, valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)

    xtdb_octopoes_service.recalculate_bits()

    event_manager.complete_process_events(xtdb_octopoes_service)

    assert len(list(filter(lambda x: x.operation_type.value == "delete", event_manager.queue))) == 0
    assert xtdb_octopoes_service.ooi_repository.list_oois({OOI}, valid_time).count == 16

    nxd = NXDOMAIN(hostname=hostname.reference)
    xtdb_octopoes_service.ooi_repository.save(nxd, valid_time)

    nxd_origin = Origin(
        origin_type=OriginType.OBSERVATION,
        method="",
        source=network.reference,
        result=[nxd.reference],
        task_id=uuid.uuid4(),
    )
    xtdb_octopoes_service.save_origin(nxd_origin, [nxd], valid_time)

    event_manager.complete_process_events(xtdb_octopoes_service)

    xtdb_octopoes_service.recalculate_bits()

    event_manager.complete_process_events(xtdb_octopoes_service)

    assert len(list(filter(lambda x: x.operation_type.value == "delete", event_manager.queue))) >= 3
    assert xtdb_octopoes_service.ooi_repository.list_oois({OOI}, valid_time).count == 4


def test_easy_chain_deletion(xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime):
    network = Network(name="internet")

    network_origin = Origin(
        origin_type=OriginType.DECLARATION,
        method="A",
        source=network.reference,
        result=[network.reference],
        task_id=uuid.uuid4(),
    )
    xtdb_octopoes_service.save_origin(network_origin, [network], valid_time)

    def chain(source, results):
        origin = Origin(
            origin_type=OriginType.OBSERVATION,
            method="",
            source=source.reference,
            result=[result.reference for result in results],
            task_id=uuid.uuid4(),
        )
        for result in results:
            xtdb_octopoes_service.ooi_repository.save(result, valid_time)
        xtdb_octopoes_service.save_origin(origin, results, valid_time)
        event_manager.complete_process_events(xtdb_octopoes_service)
        return origin, results

    hostname = Hostname(network=network.reference, name="mispo.es")
    xtdb_octopoes_service.ooi_repository.save(hostname, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    _, ip = chain(hostname, [IPAddressV4(network=network.reference, address=ip_address("134.209.85.72"))])
    chain(ip[0], [DNSARecord(hostname=hostname.reference, address=ip[0].reference, value="134.209.85.72")])

    software = Software(name="ACME")
    instance = SoftwareInstance(ooi=ip[0].reference, software=software.reference)
    xtdb_octopoes_service.ooi_repository.save(software, valid_time)
    xtdb_octopoes_service.ooi_repository.save(instance, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    count = xtdb_octopoes_service.ooi_repository.list_oois({OOI}, valid_time).count

    xtdb_octopoes_service.ooi_repository.delete_if_exists(ip[0].reference, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert xtdb_octopoes_service.ooi_repository.list_oois({OOI}, valid_time).count < count
    assert len(list(filter(lambda x: x.operation_type.value == "delete", event_manager.queue))) > 0


def test_basic_chain_deletion(xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime):
    def chain(source, results):
        origin = Origin(
            origin_type=OriginType.OBSERVATION,
            method="",
            source=source.reference,
            result=[result.reference for result in results],
            task_id=uuid.uuid4(),
        )
        for result in results:
            xtdb_octopoes_service.ooi_repository.save(result, valid_time)
        xtdb_octopoes_service.save_origin(origin, results, valid_time)
        event_manager.complete_process_events(xtdb_octopoes_service)
        return origin, results

    software1 = Software(name="ACME", version="v1")
    xtdb_octopoes_service.ooi_repository.save(software1, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    chain(software1, [Software(name="ACME", version="v2")])

    xtdb_octopoes_service.ooi_repository.delete_if_exists(software1.reference, valid_time)
    event_manager.complete_process_events(xtdb_octopoes_service)

    assert xtdb_octopoes_service.ooi_repository.list_oois({OOI}, valid_time).count == 0
    assert len(list(filter(lambda x: x.operation_type.value == "delete", event_manager.queue))) > 0


def test_affirming_ooi_delete(octopoes_api_connector: OctopoesAPIConnector, valid_time: datetime):
    # Make an object A
    network = Network(name="internet")
    octopoes_api_connector.save_declaration(Declaration(ooi=network, valid_time=valid_time))

    # Observe an object B "derived" by A
    url = "mispo.es"
    hostname = Hostname(network=network.reference, name=url)
    hostname_origin = Observation(
        method="",
        source=network.reference,
        source_method=None,
        result=[hostname],
        task_id=uuid.uuid4(),
        valid_time=valid_time,
    )
    octopoes_api_connector.save_observation(hostname_origin)
    time.sleep(1)
    assert octopoes_api_connector.list_objects({Hostname}, valid_time).count == 1

    # Delete A and validate B is not present
    octopoes_api_connector.delete(network.reference, valid_time)
    time.sleep(1)
    assert octopoes_api_connector.list_objects({Hostname}, valid_time).count == 0

    # Re-observe an object B "derived" by A
    octopoes_api_connector.save_declaration(Declaration(ooi=network, valid_time=valid_time))
    octopoes_api_connector.save_observation(hostname_origin)
    time.sleep(1)
    assert octopoes_api_connector.list_objects({Hostname}, valid_time).count == 1

    # Affirm object B
    octopoes_api_connector.save_affirmation(
        Affirmation(ooi=hostname, source_method=None, task_id=uuid.uuid4(), valid_time=valid_time)
    )
    time.sleep(1)

    # Delete A and validate B is not present
    octopoes_api_connector.delete(network.reference, valid_time)
    time.sleep(1)
    assert octopoes_api_connector.list_objects({Hostname}, valid_time).count == 0


def test_delecration_ooi_delete(octopoes_api_connector: OctopoesAPIConnector, valid_time: datetime):
    # Make an object A
    network = Network(name="internet")
    octopoes_api_connector.save_declaration(Declaration(ooi=network, valid_time=valid_time))

    # Observe an object B "derived" by A
    url = "mispo.es"
    hostname = Hostname(network=network.reference, name=url)
    hostname_origin = Observation(
        method="",
        source=network.reference,
        source_method=None,
        result=[hostname],
        task_id=uuid.uuid4(),
        valid_time=valid_time,
    )
    octopoes_api_connector.save_observation(hostname_origin)
    time.sleep(1)
    assert octopoes_api_connector.list_objects({Hostname}, valid_time).count == 1

    # Delete A and validate B is not present
    octopoes_api_connector.delete(network.reference, valid_time)
    time.sleep(1)
    assert octopoes_api_connector.list_objects({Hostname}, valid_time).count == 0

    # Re-observe an object B "derived" by A
    octopoes_api_connector.save_declaration(Declaration(ooi=network, valid_time=valid_time))
    octopoes_api_connector.save_observation(hostname_origin)
    time.sleep(1)
    assert octopoes_api_connector.list_objects({Hostname}, valid_time).count == 1

    # Infer object B
    octopoes_api_connector.save_declaration(
        Declaration(ooi=hostname, source_method=None, task_id=uuid.uuid4(), valid_time=valid_time)
    )
    time.sleep(1)

    # Delete A and validate B is not present
    octopoes_api_connector.delete(network.reference, valid_time)
    time.sleep(1)
    assert octopoes_api_connector.list_objects({Hostname}, valid_time).count == 1


def test_dangling_affirmation_delete(xtdb_octopoes_service: OctopoesService, event_manager: Mock, valid_time: datetime):
    app = Application(name="Acme")

    xtdb_octopoes_service.ooi_repository.save(app, valid_time)
    time.sleep(1)

    declaration = Origin(
        origin_type=OriginType.DECLARATION,
        method="",
        source=app.reference,
        result=[app.reference],
        task_id=uuid.uuid4(),
    )

    xtdb_octopoes_service.save_origin(declaration, [app], valid_time)
    time.sleep(1)
    event_manager.complete_process_events(xtdb_octopoes_service)
    time.sleep(1)

    assert xtdb_octopoes_service.list_ooi({Application}, valid_time).count == 1
    assert (
        len(
            xtdb_octopoes_service.origin_repository.list_origins(
                origin_type=OriginType.DECLARATION, valid_time=valid_time
            )
        )
        == 1
    )

    xtdb_octopoes_service.origin_repository.delete(declaration, valid_time)
    time.sleep(1)
    event_manager.complete_process_events(xtdb_octopoes_service)
    time.sleep(1)

    assert xtdb_octopoes_service.list_ooi({Application}, valid_time).count == 0
    assert (
        len(
            xtdb_octopoes_service.origin_repository.list_origins(
                origin_type=OriginType.DECLARATION, valid_time=valid_time
            )
        )
        == 0
    )

    xtdb_octopoes_service.ooi_repository.save(app, valid_time)
    xtdb_octopoes_service.commit()
    time.sleep(1)

    affirmation = Origin(
        origin_type=OriginType.AFFIRMATION,
        method="",
        source=app.reference,
        result=[app.reference],
        task_id=uuid.uuid4(),
    )

    xtdb_octopoes_service.save_origin(affirmation, [app], valid_time)
    time.sleep(1)
    event_manager.complete_process_events(xtdb_octopoes_service)
    time.sleep(1)

    assert xtdb_octopoes_service.list_ooi({Application}, valid_time).count == 0
    assert (
        len(
            xtdb_octopoes_service.origin_repository.list_origins(
                origin_type=OriginType.AFFIRMATION, valid_time=valid_time
            )
        )
        == 0
    )
