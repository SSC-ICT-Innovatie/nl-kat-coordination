from octopoes.models import Reference
from octopoes.models.ooi.software import Software, SoftwareInstance


def test_pipe_in_version_is_escaped_out_of_the_primary_key():
    # A banner like "1.0|evil" is attacker-controlled input (issue #5299);
    # unescaped it would corrupt the primary key of this Software and of any
    # SoftwareInstance built on it.
    software = Software(name="Foo", version="1.0|evil")

    assert software.version == "1.0%7Cevil"
    assert software.primary_key == "Software|Foo|1.0%7Cevil|"
    assert software.reference.tokenized.version == "1.0%7Cevil"


def test_pipe_in_name_and_cpe_is_escaped():
    software = Software(name="Bar|Baz", cpe="cpe:2.3:a:x:y|z")

    assert software.primary_key.count("|") == 3  # only the separators remain
    assert software.reference.tokenized.name == "Bar%7CBaz"


def test_software_instance_reference_survives_a_piped_version():
    # The original #5299 repro: SoftwareInstance's human-readable formatter
    # re-parses the software reference from the natural key and raised
    # TypeNotFound when a pipe shifted the parts.
    software = Software(name="Foo", version="1.0|evil")
    instance = SoftwareInstance(ooi=Reference.from_str("Hostname|internet|example.com"), software=software.reference)

    assert "Foo" in instance.reference.human_readable


def test_numeric_version_is_coerced_to_string():
    # External APIs (shodan, censys, binaryedge) deliver numeric versions;
    # previously this raised a ValidationError that aborted the whole scan's
    # normalization.
    assert Software(name="Foo", version=8.1).version == "8.1"
    assert Software(name="Foo", version=2025).version == "2025"


def test_clean_values_are_untouched():
    software = Software(name="nginx", version="1.24.0")

    assert software.version == "1.24.0"
    assert software.primary_key == "Software|nginx|1.24.0|"


def test_pipe_in_url_raw_is_percent_encoded():
    # A raw pipe is valid in a URL but is also the reference separator; %7C is
    # the URL's proper percent-encoding, so the URL stays equivalent.
    from octopoes.models.ooi.network import Network
    from octopoes.models.ooi.web import URL

    url = URL(network=Network(name="internet").reference, raw="https://example.com/a|b")

    assert "%7C" in str(url.raw)
    assert url.primary_key == "URL|internet|https://example.com/a%7Cb"
    assert url.reference.tokenized.raw == "https://example.com/a%7Cb"


def test_pipe_in_http_header_key_is_escaped():
    # RFC 7230 allows "|" in header names and the server controls them fully.
    from octopoes.models import Reference
    from octopoes.models.ooi.web import HTTPHeader

    resource = Reference.from_str("HTTPResource|internet|1.2.3.4|tcp|443|https|internet|x.nl|https|internet|x.nl|443|/")
    header = HTTPHeader(resource=resource, key="X-Evil|Header", value="v")

    assert header.primary_key.endswith("|X-Evil%7CHeader")
    assert header.reference.tokenized.key == "X-Evil%7CHeader"
