from ipaddress import ip_address
from unittest.mock import Mock, patch

from bits.definitions import BitDefinition

from octopoes.events.events import OOIDBEvent, OperationType, OriginDBEvent
from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddress, IPAddressV4, Network
from octopoes.models.origin import Origin, OriginType


def mocked_bit_definitions():
    return {
        "fake-hostname-bit": BitDefinition(
            id="fake-hostname-bit", consumes=Hostname, module="fake_module", parameters=[]
        ),
        "fake-ipaddress-bit": BitDefinition(id="fake-bit", consumes=IPAddress, module="fake_module", parameters=[]),
    }


@patch("octopoes.core.service.get_bit_definitions", mocked_bit_definitions)
def test_process_ooi_create_event(octopoes_service, valid_time):
    # upon creation of a new ooi
    ooi = Hostname(network=Network(name="internet").reference, name="example.com")
    octopoes_service.nibbler = Mock()
    octopoes_service.nibbler.infer.return_value = {}
    octopoes_service.process_event(
        OOIDBEvent(
            operation_type=OperationType.CREATE, valid_time=valid_time, client="_dev", old_data=None, new_data=ooi
        )
    )

    # octopoes should create a new origin, because there is a matching bit definition
    octopoes_service.origin_repository.save.assert_called_once_with(
        Origin(origin_type=OriginType.INFERENCE, method="fake-hostname-bit", source=ooi.reference), valid_time
    )


@patch("octopoes.core.service.get_bit_definitions", mocked_bit_definitions)
def test_process_event_abstract_bit_consumes(octopoes_service, valid_time):
    # upon creation of a new ooi
    ooi = IPAddressV4(network=Network(name="internet").reference, address=ip_address("1.1.1.1"))
    octopoes_service.nibbler = Mock()
    octopoes_service.nibbler.infer.return_value = {}
    octopoes_service.process_event(
        OOIDBEvent(
            operation_type=OperationType.CREATE, valid_time=valid_time, client="_dev", old_data=None, new_data=ooi
        )
    )

    # octopoes should create a new origin, because there is a matching bit definition (w/ abstract class)
    octopoes_service.origin_repository.save.assert_called_once_with(
        Origin(origin_type=OriginType.INFERENCE, method="fake-ipaddress-bit", source=ooi.reference), valid_time
    )


def test_on_update_origin(octopoes_service, valid_time):
    # when the result of an origin changes
    old_data = Origin(
        origin_type=OriginType.OBSERVATION,
        method="test-boefje",
        source=Reference.from_str("Hostname|internet|example.com"),
        result=[Reference.from_str("IPAddress|internet|1.1.1.1")],
    )
    new_data = Origin(
        origin_type=OriginType.OBSERVATION,
        method="test-boefje",
        source=Reference.from_str("Hostname|internet|example.com"),
    )
    event = OriginDBEvent(
        operation_type=OperationType.UPDATE, valid_time=valid_time, client="_dev", old_data=old_data, new_data=new_data
    )

    # and the deferenced ooi is no longer referred to by any origins
    octopoes_service.origin_repository.list_origins.return_value = []
    octopoes_service.process_event(event)

    # the ooi should be deleted
    octopoes_service.ooi_repository.delete_if_exists.assert_called_once_with(
        Reference.from_str("IPAddress|internet|1.1.1.1"), valid_time
    )
