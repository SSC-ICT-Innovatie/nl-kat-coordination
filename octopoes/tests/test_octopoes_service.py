from datetime import datetime
from ipaddress import ip_address
from unittest.mock import MagicMock, Mock, patch

import pytest
from bits.definitions import BitDefinition

from octopoes.events.events import OOIDBEvent, OperationType, OriginDBEvent, ScanProfileDBEvent
from octopoes.models import EmptyScanProfile, Reference, ScanLevel
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
    octopoes_service.origin_repository.save = MagicMock(return_value=True)
    octopoes_service.scan_profile_repository.get = MagicMock(return_value=True)
    ooi = Hostname(network=Network(name="internet").reference, name="example.com")
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
    octopoes_service.origin_repository.save = MagicMock(return_value=True)
    octopoes_service.scan_profile_repository.get = MagicMock(return_value=True)
    ooi = IPAddressV4(network=Network(name="internet").reference, address=ip_address("1.1.1.1"))
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
    octopoes_service.origin_repository.list_origins = MagicMock(return_value=[])
    octopoes_service.ooi_repository.delete_if_exists = MagicMock(return_value=[])
    octopoes_service.process_event(event)

    # the ooi should be deleted
    octopoes_service.ooi_repository.delete_if_exists.assert_called_once_with(
        Reference.from_str("IPAddress|internet|1.1.1.1"), valid_time
    )


@pytest.mark.parametrize("new_data", [EmptyScanProfile(reference="test|reference"), None])
@pytest.mark.parametrize("old_data", [EmptyScanProfile(reference="test|reference"), None])
def test_on_create_scan_profile(octopoes_service, new_data, old_data, bit_runner: MagicMock):
    octopoes_service.origin_repository.list_origins = MagicMock(
        return_value=[
            Origin(
                origin_type=OriginType.INFERENCE,
                method="check-csp-header",
                source=Reference.from_str("Hostname|internet|example.com"),
            )
        ]
    )
    octopoes_service.origin_repository.get = MagicMock(
        return_value=Origin(
            origin_type=OriginType.INFERENCE,
            method="check-csp-header",
            source=Reference.from_str("Hostname|internet|example.com"),
        )
    )
    octopoes_service.event_manager.client = "_dev"
    octopoes_service.scan_profile_repository.get = MagicMock(return_value=Mock(level=ScanLevel.L2))
    octopoes_service.ooi_repository.get = MagicMock(return_value=Network(name="internet"))
    octopoes_service.origin_parameter_repository.list_by_origin = MagicMock(return_value={})
    octopoes_service.ooi_repository.load_bulk = MagicMock(return_value={})
    octopoes_service.ooi_repository.save = MagicMock(return_value=True)

    mock_oois = [Mock(reference="test1"), Mock(reference="test2")]
    bit_runner().run = MagicMock(return_value=mock_oois)

    valid_time = datetime(2023, 1, 1)
    event = ScanProfileDBEvent(
        operation_type=OperationType.CREATE,
        valid_time=valid_time,
        old_data=old_data,
        new_data=new_data,
        reference="test|reference",
        client="_dev",
    )

    octopoes_service.process_event(event)

    assert octopoes_service.ooi_repository.save.call_count == 2
    octopoes_service.ooi_repository.save.assert_any_call(mock_oois[0], valid_time=valid_time, end_valid_time=None)
    octopoes_service.ooi_repository.save.assert_any_call(mock_oois[1], valid_time=valid_time, end_valid_time=None)
