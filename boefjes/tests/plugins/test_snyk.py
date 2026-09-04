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

    assert len(cve_fts) == 2
    assert len(snyk_fts) == 1
    assert len(kat_fts) == 1
    assert kat_fts[0].id == "KAT-SOFTWARE-UPDATE-AVAILABLE"
    # 3 vuln findings + 1 update finding = 4 Finding objects
    assert len(findings) == 4


def test_snyk_findings_severity_set():
    """Verify that severity and cvss_score are set on finding types."""
    oois = list(run(input_ooi, get_dummy_data("inputs/snyk-result-findings.json")))

    cve_fts = [o for o in oois if isinstance(o, CVEFindingType)]
    assert len(cve_fts) == 2

    high_cve = next(ft for ft in cve_fts if ft.id == "CVE-2026-4800")
    assert high_cve.risk_severity == RiskLevelSeverity.HIGH
    assert high_cve.risk_score == 8.6

    medium_cve = next(ft for ft in cve_fts if ft.id == "CVE-2026-2950")
    assert medium_cve.risk_severity == RiskLevelSeverity.MEDIUM
    assert medium_cve.risk_score == 6.9

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
    assert vuln["cvss_score"] == 8.6
    assert vuln["cve"] == "CVE-2026-4800"
    assert vuln["affected_versions"] == "<4.18.1"


def test_snyk_ecosystem_from_cpe():
    """Test that the ecosystem is derived from CPE when available."""
    from boefjes.plugins.kat_snyk.main import _ecosystem_from_cpe

    assert _ecosystem_from_cpe(None) == "npm"
    assert _ecosystem_from_cpe("cpe:2.3:a:lodash:lodash:1.0:*:*:*:*:node.js:*:*") == "npm"
    assert _ecosystem_from_cpe("cpe:2.3:a:django:django:1.0:*:*:*:*:python:*:*") == "pip"
    assert _ecosystem_from_cpe("cpe:2.3:a:spring:spring:1.0:*:*:*:*:java:*:*") == "maven"
    assert _ecosystem_from_cpe("cpe:2.3:a:rails:rails:1.0:*:*:*:*:ruby:*:*") == "rubygems"
    assert _ecosystem_from_cpe("cpe:2.3:a:unknown:pkg:1.0:*:*:*:*:*:*:*") == "npm"
