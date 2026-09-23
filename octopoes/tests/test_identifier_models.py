from octopoes.models import Reference
from octopoes.models.ooi.identifier import Identifier, IdentifierInstance, IdentifierVendor


def test_identifier_references_render_human_readable():
    vendor = IdentifierVendor(name="GoogleTagManager")
    identifier = Identifier(vendor=vendor.reference, value="GTM-12345")
    instance = IdentifierInstance(
        identifier=identifier.reference, location=Reference.from_str("Hostname|internet|example.com")
    )
    assert vendor.reference.human_readable == "Vendor of identifiers GoogleTagManager"
    assert "GTM-12345" in identifier.reference.human_readable
    assert "GoogleTagManager" in identifier.reference.human_readable
    assert "example.com" in instance.reference.human_readable


def test_identifier_instance_pk_distinguishes_location_types():
    vendor = IdentifierVendor(name="GoogleTagManager")
    identifier = Identifier(vendor=vendor.reference, value="GTM-12345")
    on_hostname = IdentifierInstance(
        identifier=identifier.reference, location=Reference.from_str("Hostname|internet|example.com")
    )
    on_zone = IdentifierInstance(
        identifier=identifier.reference, location=Reference.from_str("DNSZone|internet|example.com")
    )
    assert on_hostname.primary_key != on_zone.primary_key
