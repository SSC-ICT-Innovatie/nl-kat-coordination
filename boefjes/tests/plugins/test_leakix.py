import json
from datetime import datetime, timezone

from pydantic import TypeAdapter

import boefjes.plugins.kat_leakix.normalize as leakix_normalize
from boefjes.plugins.kat_leakix.normalize import run
from octopoes.models import Reference
from octopoes.models.ooi.certificate import (
    SubjectAlternativeNameHostname,
    SubjectAlternativeNameQualifier,
    X509Certificate,
)
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import AutonomousSystem, IPAddressV4, IPPort
from octopoes.models.ooi.software import Software, SoftwareInstance
from octopoes.models.types import OOIType
from tests.loading import get_dummy_data

# The example.com fixture was captured on 2024-02-14; freezing the clock there
# keeps time-derived attributes (X509Certificate.expires_in) deterministic so
# the full-output snapshot can be compared byte-for-byte.
FIXTURE_CAPTURE_TIME = datetime(2024, 2, 14, 13, 0, 0, tzinfo=timezone.utc)


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FIXTURE_CAPTURE_TIME if tz else FIXTURE_CAPTURE_TIME.replace(tzinfo=None)


def freeze_normalizer_clock(monkeypatch):
    monkeypatch.setattr(leakix_normalize, "datetime", FixedDatetime)


def test_output(monkeypatch):
    freeze_normalizer_clock(monkeypatch)
    input_ooi = TypeAdapter(OOIType).validate_python(
        {
            "object_type": "HostnameHTTPURL",
            "network": "Network|internet",
            "scheme": "https",
            "port": 443,
            "path": "/",
            "netloc": "Hostname|internet|example.com",
        }
    )

    output = [x for x in run(input_ooi.serialize(), get_dummy_data("raw/leakix-example.com.json"))]

    assert str(output) == get_dummy_data("raw/leakix-example.com-output.txt").decode().strip()


def _get_hostname_input_ooi():
    return TypeAdapter(OOIType).validate_python(
        {"object_type": "Hostname", "network": "Network|internet", "name": "example.com"}
    )


def test_leak_findings_are_enriched(monkeypatch):
    freeze_normalizer_clock(monkeypatch)
    input_ooi = _get_hostname_input_ooi()

    output = list(run(input_ooi.serialize(), get_dummy_data("raw/leakix-example.com.json")))
    findings = [o for o in output if o.object_type == "Finding"]

    # Leak findings now carry the event summary as proof...
    assert findings
    assert any(f.proof for f in findings)
    # ...a Plugin label never interpolates an OOI reference (the old bug was
    # 'Plugin = "IPPort|internet|..."' instead of the plugin name)...
    plugin_labels = [
        f.description.split('Plugin = "')[1] for f in findings if f.description and 'Plugin = "' in f.description
    ]
    assert plugin_labels, "expected at least one event_source-derived Plugin label"
    assert all("|" not in label for label in plugin_labels)
    # ...and the unauthenticated services in the fixture are flagged.
    assert any(f.description and "No authentication required." in f.description for f in findings)
    # The event time is included as first-seen information.
    assert any(f.description and "First seen: " in f.description for f in findings)


def test_leak_findings_bind_to_the_scanned_asset_not_the_software(monkeypatch):
    """A leak is a property of the host, not of the software product (#3211)."""
    freeze_normalizer_clock(monkeypatch)
    input_ooi = _get_hostname_input_ooi()

    output = list(run(input_ooi.serialize(), get_dummy_data("raw/leakix-example.com.json")))
    findings = [o for o in output if o.object_type == "Finding"]

    assert findings
    assert all(not str(f.ooi).startswith("Software|") for f in findings)


def test_strict_mode_filters_hostname_subdomains():
    """Test that strict mode only keeps events with exact hostname match."""
    input_ooi = _get_hostname_input_ooi()

    # Test data has 3 events: example.com (match), sub.example.com (no match), other.example.org (no match)
    output = list(run(input_ooi.serialize(), get_dummy_data("raw/leakix-hostname-strict.json")))

    # Only the exact "example.com" event should produce OOIs (6 per event:
    # AutonomousSystem, IPAddressV4, IPPort, Hostname, Software, SoftwareInstance)
    hostnames = [ooi for ooi in output if isinstance(ooi, Hostname)]
    ip_addresses = [ooi for ooi in output if isinstance(ooi, IPAddressV4)]
    ip_ports = [ooi for ooi in output if isinstance(ooi, IPPort)]

    assert len(output) == 6
    assert len(hostnames) == 1
    assert hostnames[0].name == "example.com"
    assert len(ip_addresses) == 1
    assert str(ip_addresses[0].address) == "93.184.215.14"
    assert len(ip_ports) == 1


def test_permissive_mode_keeps_all_hostname_results():
    """Test that permissive mode keeps all events including subdomains."""
    input_ooi = _get_hostname_input_ooi()

    # Load the strict test data and change search_mode to permissive
    raw_data = json.loads(get_dummy_data("raw/leakix-hostname-strict.json"))
    raw_data["search_mode"] = "permissive"

    output = list(run(input_ooi.serialize(), json.dumps(raw_data).encode()))

    # All 3 events should produce OOIs in permissive mode (6 per event)
    hostnames = [ooi for ooi in output if isinstance(ooi, Hostname)]
    ip_addresses = [ooi for ooi in output if isinstance(ooi, IPAddressV4)]

    assert len(output) == 18
    assert len(hostnames) == 3
    assert {h.name for h in hostnames} == {"example.com", "sub.example.com", "other.example.org"}
    assert len(ip_addresses) == 3


def test_no_netblocks_are_emitted():
    """Per-event network attribution is low-confidence; netblock discovery is
    left to the specialized boefjes. Only the AutonomousSystem is extracted."""
    input_ooi = _get_hostname_input_ooi()

    output = list(run(input_ooi.serialize(), get_dummy_data("raw/leakix-hostname-strict.json")))

    assert any(isinstance(ooi, AutonomousSystem) for ooi in output)
    assert all(ooi.object_type not in ("IPV4NetBlock", "IPV6NetBlock") for ooi in output)


def _run_enrichment_fixture(components: dict | None = None):
    input_ooi = _get_hostname_input_ooi()
    raw_data = json.loads(get_dummy_data("raw/leakix-enrichment.json"))
    if components is not None:
        raw_data["components"] = components
    return list(run(input_ooi.serialize(), json.dumps(raw_data).encode()))


def test_stage_only_leak_produces_finding():
    """leak.stage is a sibling of leak.dataset in l9format. The old code read
    dataset.stage (always absent), so a leak carrying only a stage was dropped."""
    output = _run_enrichment_fixture()
    findings = [o for o in output if o.object_type == "Finding"]

    stage_findings = [f for f in findings if f.description and "Stage of the leak is: open." in f.description]
    assert len(stage_findings) == 1
    finding = stage_findings[0]
    assert str(finding.finding_type) == "KATFindingType|KAT-LEAKIX-LOW"
    # The finding binds to the scanned host, not the detected software (#3211)
    assert str(finding.ooi) == "Hostname|internet|example.com"
    assert "Leak type: configuration." in finding.description


def test_cve_tags_bind_to_software():
    output = _run_enrichment_fixture()
    cve_findings = [
        o for o in output if o.object_type == "Finding" and str(o.finding_type).startswith("CVEFindingType")
    ]

    assert len(cve_findings) == 1
    # A CVE is a property of the software version; affected assets are found by
    # traversing the graph in reports, not by binding the finding per instance.
    assert str(cve_findings[0].ooi) == "Software|Apache httpd|2.4.66|"


def test_certificate_extraction_keeps_newest_observation_per_endpoint():
    output = _run_enrichment_fixture()
    certificates = [o for o in output if isinstance(o, X509Certificate)]

    # Two observations exist for example.com:443 (a renewed R12 certificate and
    # the older R11 one); only the newest may be emitted so the old certificate
    # cannot raise a false expired-certificate finding.
    assert len(certificates) == 1
    certificate = certificates[0]
    assert certificate.issuer == "R12"
    assert certificate.subject == "example.com"
    assert certificate.serial_number == "3f2a1b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708"
    assert certificate.pk_algorithm == "RSA"
    assert certificate.pk_size == 2048
    assert certificate.valid_until == "2026-08-13T00:00:00Z"


def test_certificate_sans_feed_hostname_discovery():
    output = _run_enrichment_fixture()

    san_hostnames = [o for o in output if isinstance(o, SubjectAlternativeNameHostname)]
    san_qualifiers = [o for o in output if isinstance(o, SubjectAlternativeNameQualifier)]
    hostnames = {o.name for o in output if isinstance(o, Hostname)}

    assert len(san_hostnames) == 2
    assert len(san_qualifiers) == 1
    assert san_qualifiers[0].name == "*.staging.example.com"
    # The SAN list surfaces www.example.com as a newly discovered asset
    assert "www.example.com" in hostnames


def test_software_extraction_from_headers_modules_and_os():
    output = _run_enrichment_fixture()
    software = {(o.name, o.version) for o in output if isinstance(o, Software)}

    # service.software
    assert ("Apache httpd", "2.4.66") in software
    # nested module
    assert ("PHP", "8.3.30") in software
    # Server header (the parenthesized "(Debian)" is an OS hint, not a version)
    assert ("Apache", "2.4.66") in software
    # operating system, cleaned of the parenthetical codename and kernel suffix
    assert ("Debian GNU/Linux 12", None) in software
    assert ("Debian", None) in software

    # The module nests under the parent software instance (same shape as wpscan)
    instances = [o for o in output if isinstance(o, SoftwareInstance)]
    php_instances = [i for i in instances if str(i.software) == "Software|PHP|8.3.30|"]
    assert len(php_instances) == 1
    assert str(php_instances[0].ooi).startswith("SoftwareInstance|Hostname|internet|example.com|Software|Apache httpd")


def test_ssh_banner_produces_software():
    output = _run_enrichment_fixture()
    software = {(o.name, o.version) for o in output if isinstance(o, Software)}

    assert ("OpenSSH", "9.2p1") in software


def test_outdated_tls_version_produces_finding():
    output = _run_enrichment_fixture()
    findings = [o for o in output if o.object_type == "Finding"]

    tls_findings = [f for f in findings if str(f.finding_type) == "KATFindingType|KAT-TLS-1.0-SUPPORT"]
    assert len(tls_findings) == 1
    assert "TLSv1.0" in tls_findings[0].description
    assert "TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA" in tls_findings[0].description
    # TLSv1.3 events do not produce protocol findings
    assert not any("TLSv1.3" in f.description for f in findings if f.description)


def test_components_can_be_disabled():
    output = _run_enrichment_fixture(
        components={"asn": False, "certificates": False, "software": False, "ssh": False, "tls": False}
    )

    assert not any(isinstance(o, AutonomousSystem) for o in output)
    assert not any(isinstance(o, X509Certificate) for o in output)
    assert not any(isinstance(o, Software) for o in output)
    assert not any(o.object_type == "Finding" and "KAT-TLS" in str(o.finding_type) for o in output)

    # The core output (IPs, ports, hostname, leak findings) is unaffected
    assert any(isinstance(o, IPAddressV4) for o in output)
    assert any(isinstance(o, IPPort) for o in output)
    assert any(isinstance(o, Hostname) for o in output)
    leak_findings = [o for o in output if o.object_type == "Finding" and "KAT-LEAKIX" in str(o.finding_type)]
    assert leak_findings
    # Without software extraction, the leak finding falls back to the plugin label
    assert any(f.description and 'Plugin = "WpUserEnumHttp".' in f.description for f in leak_findings)


def _run_hostdetails_fixture():
    """Run the anonymized real /host API capture (12 events, captured 2026-08)."""
    input_ooi = TypeAdapter(OOIType).validate_python(
        {"object_type": "Hostname", "network": "Network|internet", "name": "example.org"}
    )
    return list(run(input_ooi.serialize(), get_dummy_data("raw/leakix-hostdetails.json")))


def test_hostdetails_capture_keeps_newest_certificate_per_endpoint():
    output = _run_hostdetails_fixture()
    certificates = {c.serial_number[:8]: c for c in output if isinstance(c, X509Certificate)}

    # The capture holds three distinct certificates; the renewed-away one
    # (expired 2026-06-14, last seen 2026-05-09) must not be emitted, the
    # newest observation per endpoint must be: R12 on :443, R13 on :80.
    assert len(certificates) == 2
    assert "89bb2615" not in certificates
    assert certificates["72726f1a"].issuer == "R12"
    assert certificates["5ec5563e"].issuer == "R13"

    # The wildcard SAN from the live certificate becomes a qualifier
    assert any(o.name == "*.example.org" for o in output if isinstance(o, SubjectAlternativeNameQualifier))


def test_hostdetails_capture_emits_conflicting_as_but_no_netblocks():
    output = _run_hostdetails_fixture()

    # The capture reports two different AS for the same IP (LeakIX per-event
    # attribution is low-confidence); both are emitted, netblocks never.
    as_numbers = {o.number for o in output if isinstance(o, AutonomousSystem)}
    assert as_numbers == {"13127", "31798"}
    assert all(o.object_type not in ("IPV4NetBlock", "IPV6NetBlock") for o in output)


def test_hostdetails_capture_leak_binding_and_software():
    output = _run_hostdetails_fixture()

    leak_findings = [o for o in output if o.object_type == "Finding" and "KAT-LEAKIX" in str(o.finding_type)]
    assert len(leak_findings) == 1
    assert str(leak_findings[0].ooi) == "Hostname|internet|example.org"
    assert leak_findings[0].proof

    software = {(o.name, o.version) for o in output if isinstance(o, Software)}
    assert ("Apache", "2.4.66") in software  # service.software and Server header
    assert ("PHP", "8.3.30") in software  # X-Powered-By header
    assert ("Debian", None) in software  # service.software.os


def test_old_format_enables_all_components(monkeypatch):
    """Raw files from before the component toggles existed extract everything."""
    freeze_normalizer_clock(monkeypatch)
    input_ooi = _get_hostname_input_ooi()

    output = list(run(input_ooi.serialize(), get_dummy_data("raw/leakix-example.com.json")))

    assert any(isinstance(o, AutonomousSystem) for o in output)
    assert any(isinstance(o, Software) for o in output)
    # The old-format fixture contains five events with real certificates
    assert any(isinstance(o, X509Certificate) for o in output)


def test_software_pipe_never_reaches_a_primary_key():
    # #5299: a "|" (the reference separator) in a header OS hint, a service.software
    # field or a nested module must never end up in a Software primary key. A corrupt
    # name is dropped; a piped version is nulled.
    host = Reference.from_str("Hostname|internet|example.com")
    events = [
        {"http": {"header": {"server": "Apache/2.4.6 (Ubuntu|evil|x)"}}},
        {"service": {"software": {"name": "Apache", "version": "2.4.66|evil"}}},
        {"service": {"software": {"name": "Nginx|evil"}}},
        {"service": {"software": {"name": "Nginx", "modules": [{"name": "mod|evil", "version": "1|2"}]}}},
    ]
    for event in events:
        oois, _, _ = leakix_normalize.extract_software(event, host)
        for software in (o for o in oois if isinstance(o, Software)):
            assert "|" not in software.name
            assert "|" not in (software.version or "")
            # A clean Software reference is exactly "Software|name|version|cpe".
            assert str(software.reference).count("|") == 3

    # Positive control: the clean product from the first header is still extracted.
    oois, _, _ = leakix_normalize.extract_software(events[0], host)
    assert any(isinstance(o, Software) and o.name == "Apache" for o in oois)
