import json
from unittest import mock

from boefjes.plugins.kat_snyk.main import run as run_boefje
from boefjes.plugins.kat_snyk.normalize import run
from boefjes.worker.job_models import BoefjeMeta
from octopoes.models.ooi.findings import KATFindingType, RiskLevelSeverity, SnykFindingType
from octopoes.models.types import CVEFindingType, Finding
from tests.loading import get_dummy_data

input_ooi = {"primary_key": "Software|lodash|1.1.0|", "name": "lodash", "version": "1.1.0"}


def test_snyk_no_findings():
    assert not list(run(input_ooi, get_dummy_data("inputs/snyk-result-no-findings.json")))


def test_snyk_findings():
    oois = list(run(input_ooi, get_dummy_data("inputs/snyk-result-findings.json")))

    # Two CVE findings + one Snyk finding + one KAT-SOFTWARE-UPDATE-AVAILABLE
    cve_fts = [o for o in oois if isinstance(o, CVEFindingType)]
    snyk_fts = [o for o in oois if isinstance(o, SnykFindingType)]
    kat_fts = [o for o in oois if isinstance(o, KATFindingType)]
    findings = [o for o in oois if isinstance(o, Finding)]

    assert len(cve_fts) == 1
    assert len(snyk_fts) == 1
    assert len(kat_fts) == 1
    assert kat_fts[0].id == "KAT-SOFTWARE-UPDATE-AVAILABLE"
    # 2 vuln findings + 1 update finding = 3 Finding objects
    assert len(findings) == 3


def test_snyk_findings_severity_set():
    """Verify that severity is set on Snyk finding types.

    CVE findings do not carry severity/risk_score from Snyk — the CVE boefje
    hydrates those from the authoritative source.
    """
    oois = list(run(input_ooi, get_dummy_data("inputs/snyk-result-findings.json")))

    cve_fts = [o for o in oois if isinstance(o, CVEFindingType)]
    assert len(cve_fts) == 1

    # CVE findings: no severity or score from Snyk (CVE boefje hydrates)
    for cve_ft in cve_fts:
        assert cve_ft.risk_severity is None
        assert cve_ft.risk_score is None

    snyk_fts = [o for o in oois if isinstance(o, SnykFindingType)]
    assert len(snyk_fts) == 1
    assert snyk_fts[0].risk_severity == RiskLevelSeverity.HIGH
    assert snyk_fts[0].risk_score == 7.4


def test_snyk_html_parser(mocker):
    """Test that the boefje correctly parses the Nuxt SSR data from snyk.io."""
    mock_get = mocker.patch("boefjes.plugins.kat_snyk.main.requests.get")
    boefje_meta = BoefjeMeta.model_validate_json(get_dummy_data("snyk-job.json"))

    mock_response = mock.Mock()
    mock_response.text = get_dummy_data("snyk-vuln-nuxt.html").decode()
    mock_get.return_value = mock_response

    mime_types, result = run_boefje(boefje_meta.model_dump())[0]

    output = json.loads(result)

    assert len(output["vulnerabilities"]) == 12
    assert output["latest_version"] == "4.18.1"

    # Check that severity is preserved
    vuln = output["vulnerabilities"][0]
    assert vuln["severity"] == "high"
    assert vuln["cve"] == "CVE-2026-4800"
    assert vuln["affected_versions"] == "<4.18.1"
    assert vuln["cvss_score"] is not None


def test_snyk_skips_vulnerabilities_that_do_not_affect_the_installed_version():
    """A patched install must not inherit the package's whole vulnerability history."""
    patched = {"primary_key": "Software|lodash|4.18.1|", "name": "lodash", "version": "4.18.1"}
    oois = list(run(patched, get_dummy_data("inputs/snyk-result-findings.json")))

    # 4.18.1 is outside every affected range in the fixture (<4.18.1, >=4.0.0 <4.18.1, <4.17.11)
    assert [o for o in oois if isinstance(o, Finding)] == []


def test_snyk_reports_only_the_matching_ranges():
    oois = list(run(input_ooi, get_dummy_data("inputs/snyk-result-findings.json")))
    ids = {o.finding_type.tokenized.id for o in oois if isinstance(o, Finding)}

    # 1.1.0 matches <4.18.1 and <4.17.11, but not >=4.0.0,<4.18.1
    assert "CVE-2026-2950" not in ids
    assert ids == {"CVE-2026-4800", "SNYK-JS-LODASH-73638", "KAT-SOFTWARE-UPDATE-AVAILABLE"}


def test_snyk_null_severity_does_not_crash():
    """A vulnerability without a severity key yields finding OOIs instead of AttributeError."""
    raw = json.dumps({"vulnerabilities": [{"id": "SNYK-X-1", "title": "t", "severity": None}], "latest_version": None})
    oois = list(run(input_ooi, raw))

    assert isinstance(oois[0], SnykFindingType)
    assert [o for o in oois if isinstance(o, Finding)]


def test_snyk_ecosystem_from_cpe():
    """Test that the ecosystem is derived from CPE when available."""
    from boefjes.plugins.kat_snyk.main import _ecosystem_from_cpe

    assert _ecosystem_from_cpe(None) is None
    assert _ecosystem_from_cpe("cpe:2.3:a:lodash:lodash:1.0:*:*:*:*:node.js:*:*") == "npm"
    assert _ecosystem_from_cpe("cpe:2.3:a:django:django:1.0:*:*:*:*:python:*:*") == "pip"
    assert _ecosystem_from_cpe("cpe:2.3:a:spring:spring:1.0:*:*:*:*:java:*:*") == "maven"
    assert _ecosystem_from_cpe("cpe:2.3:a:rails:rails:1.0:*:*:*:*:ruby:*:*") == "rubygems"
    assert _ecosystem_from_cpe("cpe:2.3:a:unknown:pkg:1.0:*:*:*:*:*:*:*") is None


def test_snyk_fetch_disambiguates_ecosystem_by_installed_version(mocker):
    """When npm and pip both have a package with this name, the one listing the
    installed version wins — npm:django must not mask pip:django."""
    from boefjes.plugins.kat_snyk.main import _fetch_package_data

    html = get_dummy_data("snyk-vuln-nuxt.html").decode()
    npm_page = mock.Mock(status_code=200, text=html)
    npm_page.raise_for_status = mock.Mock()
    not_found = mock.Mock(status_code=404)

    def fake_get(url, timeout):
        return npm_page if url.startswith("https://snyk.io/vuln/npm:") else not_found

    mocker.patch("boefjes.plugins.kat_snyk.main.requests.get", side_effect=fake_get)

    # lodash 1.1.0 is not in the fixture's version list (all 4.x), so no ecosystem
    # matches: the first parseable page is returned as fallback.
    pkg = _fetch_package_data("lodash", "1.1.0", None)
    assert pkg is not None and len(pkg["vulnerabilities"]) == 12

    # A version that is listed resolves immediately, on the first ecosystem.
    pkg = _fetch_package_data("lodash", "4.17.21", None)
    assert pkg is not None and len(pkg["vulnerabilities"]) == 12


def test_snyk_fetch_skips_404_and_returns_none_when_nothing_parses(mocker):
    from boefjes.plugins.kat_snyk.main import _fetch_package_data

    mocker.patch("boefjes.plugins.kat_snyk.main.requests.get", return_value=mock.Mock(status_code=404))
    assert _fetch_package_data("does-not-exist", "1.0", None) is None
