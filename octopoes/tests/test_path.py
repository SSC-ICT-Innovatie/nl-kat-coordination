from unittest import TestCase
from unittest.mock import patch

from octopoes.models.path import (
    Direction,
    Path,
    Segment,
    get_max_scan_level_inheritance,
    get_paths_to_neighbours,
    incoming_step_grammar,
)
from octopoes.models.types import IPAddressV4
from tests.mocks.mock_ooi_types import (
    ALL_OOI_TYPES,
    OOITYPE_BY_NAME,
    MockDNSCNAMERecord,
    MockDNSZone,
    MockHostname,
    MockIPAddress,
    MockIPPort,
    MockLabel,
    MockNetwork,
    MockResolvedHostname,
)


@patch("octopoes.models.types.ALL_TYPES", ALL_OOI_TYPES)
@patch("octopoes.models.types.OOITYPE_BY_NAME", OOITYPE_BY_NAME)
class PathTest(TestCase):
    def test_path_outoing_relation(self):
        path = Path.parse("MockResolvedHostname.hostname")
        self.assertCountEqual(
            [Segment(MockResolvedHostname, Direction.OUTGOING, "hostname", MockHostname)], path.segments
        )

    def test_path_incoming_relation(self):
        path = Path.parse("MockHostname.<hostname [is MockResolvedHostname]")
        self.assertCountEqual(
            [Segment(MockHostname, Direction.INCOMING, "hostname", MockResolvedHostname)], path.segments
        )

    def test_path_deeper(self):
        path = Path.parse("MockDNSCNAMERecord.target_hostname.<hostname[is MockResolvedHostname].address")
        self.assertEqual(MockHostname, path.segments[0].target_type)
        self.assertEqual(MockResolvedHostname, path.segments[1].target_type)
        self.assertEqual(MockIPAddress, path.segments[2].target_type)

    def test_step_grammar_incoming(self):
        parsed = incoming_step_grammar.parse_string("<hostname [is MockResolvedHostname]")

        incoming, property_name, _, _, ooi_type, _ = parsed

        self.assertEqual(incoming, "<")
        self.assertEqual("hostname", property_name)
        self.assertEqual("MockResolvedHostname", ooi_type)

    def test_path_abstract(self):
        path = Path.parse("MockIPAddress.<address [is MockIPPort]")
        self.assertEqual(MockIPAddress, path.segments[0].source_type)
        self.assertEqual(MockIPPort, path.segments[0].target_type)

    def test_path_reverse(self):
        path = Path.parse("MockIPAddress.<address [is MockIPPort]")
        reversed_path = path.reverse()
        self.assertEqual(Segment(MockIPPort, Direction.OUTGOING, "address", MockIPAddress), reversed_path.segments[0])

    def test_path_reverse_deep(self):
        path = Path.parse("MockDNSCNAMERecord.target_hostname.<hostname[is MockResolvedHostname].address")
        reversed_path = path.reverse()

        self.assertEqual(
            Segment(MockIPAddress, Direction.INCOMING, "address", MockResolvedHostname), reversed_path.segments[0]
        )

        self.assertEqual(
            Segment(MockResolvedHostname, Direction.OUTGOING, "hostname", MockHostname), reversed_path.segments[1]
        )

        self.assertEqual(
            Segment(MockHostname, Direction.INCOMING, "target_hostname", MockDNSCNAMERecord), reversed_path.segments[2]
        )

        self.assertEqual(
            "MockIPAddress.<address[is MockResolvedHostname].hostname.<target_hostname[is MockDNSCNAMERecord]",
            str(reversed_path),
        )

    def test_path_double_reverse(self):
        path = Path.parse("MockDNSCNAMERecord.target_hostname.<hostname[is MockResolvedHostname].address")
        self.assertEqual(path, path.reverse().reverse())

    def test_get_paths_to_neighbours(self):
        neighbouring_paths = get_paths_to_neighbours(IPAddressV4)

        expected_paths = {
            Path.parse("IPAddressV4.<address [is IPPort]"),
            Path.parse("IPAddressV4.<address [is ResolvedHostname]"),
            Path.parse("IPAddressV4.network"),
        }

        self.assertTrue(expected_paths.issubset(neighbouring_paths))

    def test_get_max_inherit_scan_level_incoming(self):
        path = Path.parse("MockIPAddressV4.<address [is MockResolvedHostname]")
        self.assertEqual(4, get_max_scan_level_inheritance(path.segments[0]))

    def test_get_max_inherit_scan_level_outgoing(self):
        path = Path.parse("MockResolvedHostname.address")
        self.assertEqual(0, get_max_scan_level_inheritance(path.segments[0]))

    def test_parse_path_with_underscore_property_name(self):
        path = Path.parse("MockDNSZone.<dns_zone [is MockHostname]")
        self.assertEqual(MockDNSZone, path.segments[0].source_type)
        self.assertEqual(Direction.INCOMING, path.segments[0].direction)
        self.assertEqual("dns_zone", path.segments[0].property_name)
        self.assertEqual(MockHostname, path.segments[0].target_type)

    def test_parse_path_outgoing_abstract(self):
        path = Path.parse("MockLabel.ooi [is MockHostname].network")
        segment_0 = path.segments[0]
        segment_1 = path.segments[1]

        self.assertEqual(MockLabel, segment_0.source_type)
        self.assertEqual("ooi", segment_0.property_name)
        self.assertEqual(MockHostname, segment_0.target_type)
        self.assertEqual(Direction.OUTGOING, segment_0.direction)

        self.assertEqual(MockHostname, segment_1.source_type)
        self.assertEqual("network", segment_1.property_name)
        self.assertEqual(MockNetwork, segment_1.target_type)
        self.assertEqual(Direction.OUTGOING, segment_1.direction)
