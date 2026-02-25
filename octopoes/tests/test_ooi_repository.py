import re
from datetime import datetime
from ipaddress import IPv4Address
from typing import Literal, cast
from unittest import TestCase
from unittest.mock import Mock, patch

from octopoes.events.manager import EventManager
from octopoes.models import OOI, Reference
from octopoes.models.ooi.dns.zone import DNSZone
from octopoes.models.ooi.network import IPAddressV4, Network
from octopoes.models.path import Direction, Path, Segment
from octopoes.models.persistence import ReferenceField
from octopoes.repositories.ooi_repository import XTDBOOIRepository
from octopoes.xtdb.client import XTDBHTTPClient, XTDBSession
from tests.mocks.mock_ooi_types import (
    ALL_OOI_TYPES,
    OOITYPE_BY_NAME,
    CONCRETE_OOITYPE_BY_NAME,
    MockIPAddress,
    MockIPAddressV4,
    MockIPPort,
    MockNetwork,
)


class OOIRepositoryTest(TestCase):
    def setUp(self) -> None:
        self.event_manager = Mock(spec=EventManager)
        self.session = XTDBSession(Mock(spec=XTDBHTTPClient))
        self.repository = XTDBOOIRepository(self.event_manager, self.session)

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

    @patch("octopoes.models.types.ALL_TYPES", ALL_OOI_TYPES)
    @patch("octopoes.models.types.OOITYPE_BY_NAME", OOITYPE_BY_NAME)
    @patch("octopoes.models.types.CONCRETE_OOITYPE_BY_NAME", CONCRETE_OOITYPE_BY_NAME)
    def test_construct_neighbour_query(self):
        reference = Reference.from_str("MockIPAddressV4|internet|1.1.1.1")

        query = self.repository.construct_neighbour_query(reference)

        expected_query = """{
                    :query {
                        :find [
                            (pull ?e [
                                :xt/id
                                {:MockIPPort/_address [*]}
                                {:MockResolvedHostname/_address [*]}
                                {:MockLabel/_ooi [*]}
                                {:MockIPAddressV4/network [*]}
                            ])
                        ]
                        :in [[ _xt_id ... ]]
                        :where [[?e :xt/id _xt_id]]
                    }
                    :in-args [["MockIPAddressV4|internet|1.1.1.1"]]
                }"""

        self.assertEqual(re.sub(r"\s+", " ", expected_query), re.sub(r"\s+", " ", query))

    @patch("octopoes.models.types.ALL_TYPES", ALL_OOI_TYPES)
    @patch("octopoes.models.types.OOITYPE_BY_NAME", OOITYPE_BY_NAME)
    @patch("octopoes.models.types.CONCRETE_OOITYPE_BY_NAME", CONCRETE_OOITYPE_BY_NAME)
    def test_encode_outgoing_segment(self):
        path = Path.parse("MockIPAddressV4.network")
        self.assertEqual("MockIPAddressV4/network", path.segments[0].encode())

    @patch("octopoes.models.types.ALL_TYPES", ALL_OOI_TYPES)
    @patch("octopoes.models.types.OOITYPE_BY_NAME", OOITYPE_BY_NAME)
    @patch("octopoes.models.types.CONCRETE_OOITYPE_BY_NAME", CONCRETE_OOITYPE_BY_NAME)
    def test_encode_incoming_segment(self):
        path = Path.parse("MockIPAddressV4.<address [is MockIPPort]")
        self.assertEqual("MockIPPort/_address", path.segments[0].encode())

    @patch("octopoes.models.types.ALL_TYPES", ALL_OOI_TYPES)
    @patch("octopoes.models.types.CONCRETE_OOITYPE_BY_NAME", CONCRETE_OOITYPE_BY_NAME)
    def test_decode_outgoing_segment(self):
        self.assertEqual(
            Segment(MockIPAddressV4, Direction.OUTGOING, "network", MockNetwork),
            self.repository.decode_segment("MockIPAddressV4/network"),
        )

    @patch("octopoes.models.types.ALL_TYPES", ALL_OOI_TYPES)
    @patch("octopoes.models.types.OOITYPE_BY_NAME", OOITYPE_BY_NAME)
    @patch("octopoes.models.types.OOITYPE_BY_NAME", OOITYPE_BY_NAME)
    @patch("octopoes.models.types.CONCRETE_OOITYPE_BY_NAME", CONCRETE_OOITYPE_BY_NAME)
    def test_decode_incoming_segment(self):
        self.assertEqual(
            Segment(MockIPAddress, Direction.INCOMING, "address", MockIPPort),
            self.repository.decode_segment("MockIPPort/_address"),
        )

    @patch("octopoes.models.types.ALL_TYPES", ALL_OOI_TYPES)
    @patch("octopoes.models.types.OOITYPE_BY_NAME", OOITYPE_BY_NAME)
    @patch("octopoes.models.types.CONCRETE_OOITYPE_BY_NAME", CONCRETE_OOITYPE_BY_NAME)
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
            Reference.from_str("MockHostname|internet|example.com"), datetime.utcnow()
        )

        resolved_hostname = neighbours[Path.parse("MockHostname.<hostname[is MockResolvedHostname]")][0]
        self.assertEqual(Reference.from_str("MockIPAddressV4|internet|1.1.1.1"), resolved_hostname.address)
