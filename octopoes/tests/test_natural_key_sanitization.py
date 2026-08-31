from octopoes.models import OOI, Reference
from octopoes.models.ooi.software import Software, SoftwareInstance


def test_escaper_only_touches_the_separator():
    assert OOI._escape_natural_key_part("a|b") == "a%7Cb"
    assert OOI._escape_natural_key_part("clean") == "clean"
    # Percent signs are left alone: URLs legitimately contain percent-encoding and must not be
    # double-encoded (which would re-key every existing URL OOI).
    assert OOI._escape_natural_key_part("a%20b") == "a%20b"


def test_pipe_in_version_is_escaped_out_of_the_primary_key():
    # A banner like "1.0|evil" is attacker-controlled (issue #5299); unescaped it would corrupt the
    # primary key of this Software and of any SoftwareInstance built on it. Escaping happens while
    # constructing the key, so the stored field value stays exactly as delivered.
    software = Software(name="Foo", version="1.0|evil")

    assert software.version == "1.0|evil"  # value untouched at rest
    assert software.primary_key == "Software|Foo|1.0%7Cevil|"  # separator escaped in the key
    assert software.reference.tokenized.version == "1.0%7Cevil"


def test_pipe_in_name_and_cpe_is_escaped():
    software = Software(name="Bar|Baz", cpe="cpe:2.3:a:x:y|z")

    assert software.name == "Bar|Baz"  # value untouched
    assert software.primary_key.count("|") == 3  # only the separators remain
    assert software.reference.tokenized.name == "Bar%7CBaz"
    assert software.reference.tokenized.cpe == "cpe:2.3:a:x:y%7Cz"


def test_software_instance_reference_survives_a_piped_version():
    # The original #5299 repro: SoftwareInstance's human-readable formatter re-parses the software
    # reference from the natural key and raised TypeNotFound when a pipe shifted the parts.
    software = Software(name="Foo", version="1.0|evil")
    instance = SoftwareInstance(ooi=Reference.from_str("Hostname|internet|example.com"), software=software.reference)

    assert "Foo" in instance.reference.human_readable


def test_numeric_version_is_coerced_to_string():
    # External APIs (shodan, censys, binaryedge) deliver numeric versions; without coercion this
    # raised a ValidationError that aborted the whole scan's normalization.
    assert Software(name="Foo", version=8.1).version == "8.1"
    assert Software(name="Foo", version=2025).version == "2025"


def test_clean_values_are_untouched():
    software = Software(name="nginx", version="1.24.0")

    assert software.version == "1.24.0"
    assert software.primary_key == "Software|nginx|1.24.0|"


def test_pipe_in_url_stays_clean_at_rest_and_is_escaped_in_the_key():
    from octopoes.models.ooi.network import Network
    from octopoes.models.ooi.web import URL

    url = URL(network=Network(name="internet").reference, raw="https://example.com/a|b")

    assert str(url.raw) == "https://example.com/a|b"  # value untouched
    assert url.primary_key == "URL|internet|https://example.com/a%7Cb"
    assert url.reference.tokenized.raw == "https://example.com/a%7Cb"


def test_percent_encoding_in_url_is_not_double_encoded():
    # |-only escaping leaves legitimate percent-encoding intact (regression guard against a
    # %-escaping scheme that would re-key every existing URL).
    from octopoes.models.ooi.network import Network
    from octopoes.models.ooi.web import URL

    url = URL(network=Network(name="internet").reference, raw="https://example.com/a%20b")

    assert url.primary_key == "URL|internet|https://example.com/a%20b"


def test_pipe_in_http_header_key_is_escaped():
    from octopoes.models.ooi.web import HTTPHeader

    resource = Reference.from_str("HTTPResource|internet|1.2.3.4|tcp|443|https|internet|x.nl|https|internet|x.nl|443|/")
    header = HTTPHeader(resource=resource, key="X-Evil|Header", value="v")

    assert header.key == "X-Evil|Header"  # value untouched
    assert header.primary_key.endswith("|X-Evil%7CHeader")
    assert header.reference.tokenized.key == "X-Evil%7CHeader"


def test_hashing_record_survives_a_piped_value():
    # DNS records hash their (attacker-controlled) value into the key. The value is escaped before the
    # hash-replace, so a pipe can neither corrupt the key nor slip past the hashing.
    from octopoes.models.ooi.dns.records import DNSTXTRecord
    from octopoes.models.ooi.dns.zone import Hostname
    from octopoes.models.ooi.network import Network

    hostname = Hostname(network=Network(name="internet").reference, name="example.com")
    record = DNSTXTRecord(hostname=hostname.reference, value="a|b|c")

    assert record.value == "a|b|c"  # value untouched at rest
    assert record.primary_key.count("|") == 3  # only the separators; the value became a clean hash
    assert record.reference.tokenized.value != "a|b|c"  # hashed, not the raw value


def test_hashing_record_with_empty_value_is_not_corrupted():
    # An empty value must not turn the hash-replace into a no-op that mangles the key (Jan's guard).
    from octopoes.models.ooi.dns.records import DNSTXTRecord
    from octopoes.models.ooi.dns.zone import Hostname
    from octopoes.models.ooi.network import Network

    hostname = Hostname(network=Network(name="internet").reference, name="example.com")
    record = DNSTXTRecord(hostname=hostname.reference, value="")

    assert record.primary_key == "DNSTXTRecord|internet|example.com|"


def test_every_concrete_type_uses_the_base_escaper():
    # No concrete OOI type may weaken the sanitisation by shadowing the escaper with a no-op; the
    # single-spot guarantee (issue #5299) depends on every type sharing the base implementation.
    from octopoes.models.types import get_concrete_types

    for ooi_type in get_concrete_types():
        assert ooi_type._escape_natural_key_part("a|b") == "a%7Cb"
