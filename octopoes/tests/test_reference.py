from ipaddress import ip_address
from unittest import TestCase
from unittest.mock import patch

from octopoes.models import Reference
from tests.mocks.mock_ooi_types import ALL_OOI_TYPES, OOITYPE_BY_NAME, MockIPAddressV4, MockNetwork


@patch("octopoes.models.types.ALL_TYPES", ALL_OOI_TYPES)
@patch("octopoes.models.types.OOITYPE_BY_NAME", OOITYPE_BY_NAME)
class ReferenceTest(TestCase):
    def test_reference(self):
        network_reference = Reference("MockNetwork|internet")
        self.assertEqual("MockNetwork", network_reference.class_)

    def test_reference_from_str(self):
        network_reference = Reference.from_str("MockNetwork|internet")
        self.assertEqual(MockNetwork, network_reference.class_type)

    def test_reference_in_model(self):
        ip = MockIPAddressV4(network="MockNetwork|internet", address=ip_address("1.1.1.1"))
        self.assertEqual(Reference("MockNetwork|internet"), ip.network)

    def test_ref_equality(self):
        a = Reference("A|KeyA")
        b = Reference("A|KeyA")
        self.assertEqual(a, b)

    def test_parse_obj(self):
        ip = MockIPAddressV4.model_validate({"address": "1.1.1.1", "network": "MockNetwork|internet"})
        self.assertEqual(Reference("MockNetwork|internet"), ip.network)
