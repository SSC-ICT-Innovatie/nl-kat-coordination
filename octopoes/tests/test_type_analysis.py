from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from octopoes.models import OOI
from octopoes.models.pagination import Paginated
from octopoes.models.types import get_collapsed_types, get_relations, to_concrete, type_by_name
from tests.mocks.mock_ooi_types import (
    ALL_OOI_TYPES,
    CONCRETE_OOITYPE_BY_NAME,
    OOITYPE_BY_NAME,
    MockDNSCNAMERecord,
    MockDNSZone,
    MockHostname,
    MockIPAddress,
    MockIPAddressV4,
    MockIPAddressV6,
    MockIPPort,
    MockLabel,
    MockNetwork,
    MockOOIType,
    MockResolvedHostname,
)


def get_concrete_types() -> set[type[OOI]]:
    return {t for t in ALL_OOI_TYPES if not t.strict_subclasses()}


def get_abstract_types() -> set[type[OOI]]:
    return {t for t in ALL_OOI_TYPES if t.strict_subclasses()}


@patch("octopoes.models.types.ALL_TYPES", ALL_OOI_TYPES)
@patch("octopoes.models.types.OOITYPE_BY_NAME", OOITYPE_BY_NAME)
@patch("octopoes.models.types.CONCRETE_OOITYPE_BY_NAME", CONCRETE_OOITYPE_BY_NAME)
@patch("octopoes.models.types.get_concrete_types", get_concrete_types)
@patch("octopoes.models.types.get_abstract_types", get_abstract_types)
class TypeSystemTest(TestCase):
    def test_concrete_types(self):
        self.assertSetEqual(
            {
                MockNetwork,
                MockIPAddressV4,
                MockIPAddressV6,
                MockIPPort,
                MockHostname,
                MockResolvedHostname,
                MockDNSCNAMERecord,
                MockDNSZone,
                MockLabel,
            },
            get_concrete_types(),
        )

    def test_abstract_types(self):
        self.assertSetEqual({OOI, MockIPAddress}, get_abstract_types())

    def test_collapsed_types(self):
        self.assertSetEqual(
            {
                MockIPAddress,
                MockIPPort,
                MockNetwork,
                MockHostname,
                MockResolvedHostname,
                MockDNSCNAMERecord,
                MockDNSZone,
                MockLabel,
            },
            get_collapsed_types(),
        )

    def test_abstract_to_concrete(self):
        self.assertEqual({MockIPAddressV4, MockIPAddressV6}, to_concrete({MockIPAddress}))

    def test_ooi_to_concrete(self):
        self.assertSetEqual(
            {
                MockNetwork,
                MockIPAddressV4,
                MockIPAddressV6,
                MockIPPort,
                MockHostname,
                MockResolvedHostname,
                MockDNSCNAMERecord,
                MockDNSZone,
                MockLabel,
            },
            to_concrete({OOI}),
        )

    def test_concrete_to_concrete(self):
        self.assertSetEqual({MockIPAddressV4}, to_concrete({MockIPAddressV4}))

    def test_type_by_name(self):
        self.assertEqual(MockIPAddressV4, type_by_name("MockIPAddressV4"))

    def test_get_relations(self):
        self.assertEqual({"network": MockNetwork}, get_relations(MockIPAddressV4))

    def test_get_relations_abstract_class(self):
        self.assertEqual({"address": MockIPAddress}, get_relations(MockIPPort))

    def test_paginated(self):
        with pytest.raises(ValidationError):
            Paginated.model_validate({"items": []})

        with pytest.raises(ValidationError):
            Paginated.model_validate({"count": 0})

        Paginated.model_validate({"count": 0, "items": []})
        Paginated.model_validate({"count": 0, "items": ["a"]})
        Paginated[MockOOIType].model_validate({"count": 0, "items": []})

        with pytest.raises(ValidationError):
            Paginated[MockOOIType].model_validate({"count": 0, "items": ["a"]})

        Paginated[MockOOIType].model_validate({"count": 0, "items": [MockNetwork(name="test")]})
