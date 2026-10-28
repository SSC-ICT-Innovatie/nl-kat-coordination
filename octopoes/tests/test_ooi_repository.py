import re
from datetime import UTC, datetime
from ipaddress import IPv4Address
from typing import Literal, cast
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

import octopoes.models.path as path_module
from octopoes.api.models import (
    Affirmation,
    Declaration,
    Observation,
    ValidatedAffirmation,
    ValidatedDeclaration,
    ValidatedObservation,
)
from octopoes.events.manager import EventManager
from octopoes.models import OOI, Reference
from octopoes.models.ooi.dns.zone import DNSZone
from octopoes.models.ooi.findings import KATFindingType
from octopoes.models.ooi.network import IPAddressV4, Network
from octopoes.models.path import _cached_paths_to_neighbours
from octopoes.models.persistence import ReferenceField
from octopoes.repositories.ooi_repository import XTDBOOIRepository, merge_ooi
from octopoes.xtdb.client import XTDBHTTPClient, XTDBSession
from tests.mocks.mock_ooi_types import (
    ALL_OOI_TYPES,
    OOITYPE_BY_NAME,
    MockIPAddress,
    MockIPAddressV4,
    MockIPPort,
    MockNetwork,
)


@patch("octopoes.models.types.ALL_TYPES", ALL_OOI_TYPES)
@patch("octopoes.models.types.OOITYPE_BY_NAME", OOITYPE_BY_NAME)
class OOIRepositoryTest(TestCase):
    def setUp(self) -> None:
        self.event_manager = Mock(spec=EventManager)
        self.session = XTDBSession(Mock(spec=XTDBHTTPClient))
        self.repository = XTDBOOIRepository(self.event_manager, self.session)

        # patch the dictionary in the path module
        path_module.OOITYPE_BY_NAME = OOITYPE_BY_NAME
        # replace cached function with uncached version
        path_module._cached_paths_to_neighbours = _cached_paths_to_neighbours.__wrapped__

    def test_node_from_ooi(self):
        internet = Network(name="internet")
        ip = IPAddressV4(network=internet.reference, address=IPv4Address("1.1.1.1"))
        serial = self.repository.serialize(ip)
        self.assertEqual("Network|internet", serial["IPAddressV4/network"])
        self.assertEqual("1.1.1.1", serial["IPAddressV4/address"])
        self.assertEqual("IPAddressV4|internet|1.1.1.1", serial["xt/id"])
        self.assertNotIn("IPAddressV4/object_type", serial)

    def test_node_from_ooi_with_list(self):
        class TestOOIClass(OOI):
            object_type: Literal["TestOOIClass"] = "TestOOIClass"
            id: str = "test_id"
            multiple_refs: list[Reference] = ReferenceField(Network)
            _natural_key_attrs = ["id"]

        internet = Network(name="internet")
        internet2 = Network(name="internet2")
        test = TestOOIClass(multiple_refs=[internet.reference, internet2.reference])
        serial = self.repository.serialize(test)
        self.assertEqual(["Network|internet", "Network|internet2"], serial["TestOOIClass/multiple_refs"])
        self.assertEqual("TestOOIClass|test_id", serial["xt/id"])

    def test_extract_node(self):
        internet = Network(name="internet")
        raw_node = {
            "xt/id": "DNSZone|internet|test.nl",
            "object_type": "DNSZone",
            "DNSZone/object_type": "DNSZone",
            "DNSZone/hostname": "Hostname|internet|test.nl",
            "DNSZone/name_servers": [],
        }

        serial = cast(DNSZone, self.repository.deserialize(raw_node))
        self.assertEqual("DNSZone", serial.object_type)
        self.assertEqual(internet.name, serial.hostname.tokenized.network.name)
        self.assertEqual("test.nl", serial.hostname.tokenized.name)

    def test_construct_neighbour_query(self):
        reference = Reference.from_str("IPPort|80")

        query = self.repository.construct_neighbour_query(reference)

        expected_query = """{
                    :query {
                        :find [
                            (pull ?e [
                                :xt/id
                                {:IPService/_ip_port [*]}
                                {:EmailAddressInstance/_location [*]}
                                {:IdentifierInstance/_location [*]}
                                {:Config/_ooi [*]}
                                {:Finding/_ooi [*]}
                                {:GeographicPoint/_ooi [*]}
                                {:Question/_ooi [*]}
                                {:SoftwareInstance/_ooi [*]}
                                {:IPPort/address [*]}
                            ])
                        ]
                        :in [[ _xt_id ... ]]
                        :where [[?e :xt/id _xt_id]]
                    }
                    :in-args [["IPPort|80"]]
                }"""

        self.assertEqual(re.sub(r"\s+", " ", expected_query), re.sub(r"\s+", " ", query))

    def test_encode_outgoing_segment(self):
        path = path_module.Path.parse("MockIPAddressV4.network")
        self.assertEqual("MockIPAddressV4/network", path.segments[0].encode())

    def test_encode_incoming_segment(self):
        path = path_module.Path.parse("MockIPAddressV4.<address [is MockIPPort]")
        self.assertEqual("MockIPPort/_address", path.segments[0].encode())

    def test_decode_outgoing_segment(self):
        self.assertEqual(
            path_module.Segment(MockIPAddressV4, path_module.Direction.OUTGOING, "network", MockNetwork),
            self.repository.decode_segment("MockIPAddressV4/network"),
        )

    def test_decode_incoming_segment(self):
        self.assertEqual(
            path_module.Segment(MockIPAddress, path_module.Direction.INCOMING, "address", MockIPPort),
            self.repository.decode_segment("MockIPPort/_address"),
        )

    def test_get_neighbours(self):
        self.session.client.query.return_value = [
            [
                {
                    "MockHostname/fqdn": {},
                    "MockResolvedHostname/_hostname": {
                        "MockResolvedHostname/address": "MockIPAddressV4|internet|1.1.1.1",
                        "MockResolvedHostname/hostname": "MockHostname|internet|example.com",
                        "xt/id": "MockResolvedHostname|internet|example.com|internet|1.1.1.1",
                        "object_type": "MockResolvedHostname",
                    },
                    "xt/id": "MockHostname|internet|example.com",
                }
            ]
        ]

        neighbours = self.repository.get_neighbours(
            Reference.from_str("MockHostname|internet|example.com"), datetime.now(UTC)
        )

        resolved_hostname = neighbours[path_module.Path.parse("MockHostname.<hostname[is MockResolvedHostname]")][0]
        self.assertEqual(Reference.from_str("MockIPAddressV4|internet|1.1.1.1"), resolved_hostname.address)


def test_kat_finding_type_omitted_classification_survives_api_round_trip():
    """A partial declaration must not turn missing metadata into [] on the wire."""
    finding_type = KATFindingType(id="KAT-NO-HSTS")
    declaration = Declaration(ooi=finding_type, valid_time=datetime.now(timezone.utc))
    payload = declaration.model_dump(mode="json")

    assert "groups" not in payload["ooi"]
    assert "tags" not in payload["ooi"]

    received = ValidatedDeclaration.model_validate(payload).ooi
    assert isinstance(received, KATFindingType)
    assert received.groups == []
    assert received.tags == []
    assert "groups" not in received.model_fields_set
    assert "tags" not in received.model_fields_set


def test_kat_finding_type_omitted_classification_survives_other_origin_requests():
    finding_type = KATFindingType(id="KAT-NO-HSTS")
    valid_time = datetime.now(timezone.utc)
    affirmation = Affirmation(ooi=finding_type, valid_time=valid_time)
    affirmation_payload = affirmation.model_dump(mode="json")
    assert "groups" not in affirmation_payload["ooi"]
    assert "tags" not in affirmation_payload["ooi"]
    restored_affirmation = ValidatedAffirmation.model_validate(affirmation_payload).ooi
    assert "groups" not in restored_affirmation.model_fields_set
    assert "tags" not in restored_affirmation.model_fields_set

    observation = Observation(
        method="unit-test",
        source=finding_type.reference,
        source_method=None,
        result=[finding_type],
        valid_time=valid_time,
        task_id=uuid4(),
    )
    observation_payload = observation.model_dump(mode="json")
    assert "groups" not in observation_payload["result"][0]
    assert "tags" not in observation_payload["result"][0]
    restored_observation = ValidatedObservation.model_validate(observation_payload).result[0]
    assert "groups" not in restored_observation.model_fields_set
    assert "tags" not in restored_observation.model_fields_set


def test_kat_finding_type_partial_merge_preserves_groups_and_tags():
    stored = KATFindingType(
        id="KAT-NO-HSTS", name="HSTS", groups=["web-security", "http-security-headers"], tags=["misconfiguration"]
    )
    partial = KATFindingType(id="KAT-NO-HSTS")
    merged, changed = merge_ooi(partial, stored)

    assert not changed
    assert merged.name == "HSTS"
    assert merged.groups == stored.groups
    assert merged.tags == stored.tags


def test_kat_finding_type_explicit_empty_classification_clears_existing_values():
    stored = KATFindingType(id="KAT-NO-HSTS", groups=["web-security"], tags=["misconfiguration"])
    explicit_clear = KATFindingType(id="KAT-NO-HSTS", groups=[], tags=[])
    payload = Declaration(ooi=explicit_clear, valid_time=datetime.now(timezone.utc)).model_dump(mode="json")
    received = ValidatedDeclaration.model_validate(payload).ooi

    assert payload["ooi"]["groups"] == []
    assert payload["ooi"]["tags"] == []
    merged, changed = merge_ooi(received, stored)
    assert changed
    assert merged.groups == []
    assert merged.tags == []


def test_kat_finding_type_partial_classification_update_keeps_other_field():
    stored = KATFindingType(id="KAT-NO-HSTS", groups=["web-security"], tags=["misconfiguration"])
    update = KATFindingType(id="KAT-NO-HSTS", groups=["http-security-headers"])
    merged, changed = merge_ooi(update, stored)

    assert changed
    assert merged.groups == ["http-security-headers"]
    assert merged.tags == ["misconfiguration"]


def test_kat_finding_type_xtdb_serialization_of_classification():
    repository = XTDBOOIRepository(Mock(spec=EventManager), XTDBSession(Mock(spec=XTDBHTTPClient)))
    classified = KATFindingType(id="KAT-NO-HSTS", groups=["web-security"], tags=["misconfiguration"])
    serial = repository.serialize(classified)

    assert serial["KATFindingType/groups"] == ["web-security"]
    assert serial["KATFindingType/tags"] == ["misconfiguration"]
    restored = repository.deserialize(serial)
    assert isinstance(restored, KATFindingType)
    assert restored.groups == classified.groups
    assert restored.tags == classified.tags

    legacy = repository.serialize(KATFindingType(id="KAT-UNKNOWN"))
    assert "KATFindingType/groups" not in legacy
    assert "KATFindingType/tags" not in legacy


def test_kat_finding_type_backfill_adds_previously_missing_classification():
    """Existing OOIs without metadata must be updated by catalog rehydration."""
    legacy = KATFindingType(id="KAT-NO-HSTS", name="HSTS")
    hydrated = KATFindingType(
        id="KAT-NO-HSTS", groups=["web-security", "http-security-headers"], tags=["misconfiguration"]
    )

    merged, changed = merge_ooi(hydrated, legacy)

    assert changed
    assert merged.groups == hydrated.groups
    assert merged.tags == hydrated.tags
    assert merged.name == "HSTS"
