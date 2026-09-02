import time

from bits.parse_csp.parse_csp import run

from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import CSPDirective, CSPSource, HTTPHeader

RESOURCE = "HTTPResource|internet|1.1.1.1|tcp|443|https|internet|example.com|https|internet|example.com|443|/"


def _csp_header(value: str) -> HTTPHeader:
    return HTTPHeader(resource=Reference.from_str(RESOURCE), key="Content-Security-Policy", value=value)


def test_non_csp_header_is_ignored():
    header = HTTPHeader(resource=Reference.from_str(RESOURCE), key="Content-Type", value="text/html")

    assert list(run(header, [], {})) == []


def test_parses_directives_and_sources():
    header = _csp_header("default-src 'self'; script-src 'self' https://cdn.example.com")

    results = list(run(header, [], {}))

    directives = [o for o in results if isinstance(o, CSPDirective)]
    sources = [o for o in results if isinstance(o, CSPSource)]
    assert {d.name for d in directives} == {"default-src", "script-src"}
    assert {s.value for s in sources} == {"'self'", "https://cdn.example.com"}
    # each source references its own directive
    script_src = next(d for d in directives if d.name == "script-src")
    assert any(s.directive == script_src.reference and s.value == "https://cdn.example.com" for s in sources)
    # a clean policy produces no parse finding
    assert not any(isinstance(o, Finding) for o in results)


def test_directive_without_value_yields_finding():
    header = _csp_header("script-src")

    results = list(run(header, [], {}))

    assert any(isinstance(o, CSPDirective) and o.name == "script-src" for o in results)
    assert KATFindingType(id="KAT-CSP-INVALID") in results
    finding = next(o for o in results if isinstance(o, Finding))
    assert "has no value" in finding.description
    assert finding.ooi == header.reference


def test_duplicate_directive_is_flagged_and_deduped():
    header = _csp_header("script-src 'self'; script-src https://a.example.com")

    results = list(run(header, [], {}))

    directives = [o for o in results if isinstance(o, CSPDirective) and o.name == "script-src"]
    assert len(directives) == 1  # the second occurrence is not emitted again
    finding = next(o for o in results if isinstance(o, Finding))
    assert "Duplicate CSP directive: script-src" in finding.description


def test_case_and_whitespace_are_normalised():
    header = _csp_header("  Default-Src   'self'  ")

    directive = next(o for o in run(header, [], {}) if isinstance(o, CSPDirective))

    assert directive.name == "default-src"


def test_parser_is_linear_on_adversarial_input():
    # The old regex-based checker was exponential: `default-src *` + ".-" * 40 stalled the worker ~18s.
    # The deterministic parser must handle the same input in well under a second (#4329 ReDoS guard).
    header = _csp_header("default-src *" + ".-" * 40 + "!")

    start = time.perf_counter()
    list(run(header, [], {}))

    assert time.perf_counter() - start < 0.1
