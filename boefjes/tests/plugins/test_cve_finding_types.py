import json

from boefjes.normalizer_models import NormalizerAffirmation
from boefjes.plugins.kat_cve_finding_types.normalize import run
from octopoes.models.ooi.findings import RiskLevelSeverity
from octopoes.models.types import CVEFindingType
from tests.loading import get_dummy_data


def test_cve_with_cvss():
    input_ooi = {"id": "CVE-2021-46882"}

    oois = list(run(input_ooi, get_dummy_data("inputs/cve-result-with-cvss.json")))

    expected = [
        NormalizerAffirmation(
            ooi=CVEFindingType(
                id="CVE-2021-46882",
                description="The video framework has memory overwriting caused by addition overflow. "
                "Successful exploitation of this vulnerability may affect availability.",
                source="https://cve.circl.lu/cve/CVE-2021-46882",
                risk_severity=RiskLevelSeverity.HIGH,
                risk_score=7.5,
            )
        )
    ]

    assert expected == oois


def test_cve_with_cvss2():
    input_ooi = {"id": "CVE-2016-0616"}

    oois = list(run(input_ooi, get_dummy_data("inputs/cve-result-with-cvss2.json")))

    expected = [
        NormalizerAffirmation(
            ooi=CVEFindingType(
                id="CVE-2016-0616",
                description="Unspecified vulnerability in Oracle MySQL 5.5.46 and earlier and MariaDB before "
                "5.5.47, 10.0.x before 10.0.23, and 10.1.x before 10.1.10 allows remote authenticated users "
                "to affect availability via unknown vectors related to Optimizer.",
                source="https://cve.circl.lu/cve/CVE-2016-0616",
                risk_severity=RiskLevelSeverity.MEDIUM,
                risk_score=4.0,
            )
        )
    ]

    assert expected == oois


def test_cve_with_only_cvss_v4():
    # NVD may score a CVE only with CVSS v4.0. The old code fell through to
    # metrics["cvssMetricV2"] and raised KeyError, aborting the normalizer.
    input_ooi = {"id": "CVE-2024-12345"}

    oois = list(run(input_ooi, get_dummy_data("inputs/cve-result-with-cvss4.json")))

    expected = [
        NormalizerAffirmation(
            ooi=CVEFindingType(
                id="CVE-2024-12345",
                description="An example vulnerability scored only with CVSS v4.0.",
                source="https://cve.circl.lu/cve/CVE-2024-12345",
                risk_severity=RiskLevelSeverity.CRITICAL,
                risk_score=9.3,
            )
        )
    ]

    assert expected == oois


def test_cve_with_empty_metric_list():
    # A metric key that is present but holds an empty list used to raise
    # IndexError on cvss[0]; it should fall back to UNKNOWN instead.
    input_ooi = {"id": "CVE-2024-0001"}
    raw = json.dumps(
        {
            "cve": {
                "descriptions": [{"lang": "en", "value": "A CVE with an empty metric list."}],
                "metrics": {"cvssMetricV31": []},
            }
        }
    ).encode()

    oois = list(run(input_ooi, raw))

    expected = [
        NormalizerAffirmation(
            ooi=CVEFindingType(
                id="CVE-2024-0001",
                description="A CVE with an empty metric list.",
                source="https://cve.circl.lu/cve/CVE-2024-0001",
                risk_severity=RiskLevelSeverity.UNKNOWN,
                risk_score=None,
            )
        )
    ]

    assert expected == oois


def test_cve_with_empty_preferred_metric_falls_through():
    # An empty preferred metric list should not shadow a populated lower-priority one.
    input_ooi = {"id": "CVE-2024-0002"}
    raw = json.dumps(
        {
            "cve": {
                "descriptions": [{"lang": "en", "value": "A CVE with an empty v3.1 list and a populated v2 list."}],
                "metrics": {"cvssMetricV31": [], "cvssMetricV2": [{"type": "Primary", "cvssData": {"baseScore": 5.0}}]},
            }
        }
    ).encode()

    oois = list(run(input_ooi, raw))

    expected = [
        NormalizerAffirmation(
            ooi=CVEFindingType(
                id="CVE-2024-0002",
                description="A CVE with an empty v3.1 list and a populated v2 list.",
                source="https://cve.circl.lu/cve/CVE-2024-0002",
                risk_severity=RiskLevelSeverity.MEDIUM,
                risk_score=5.0,
            )
        )
    ]

    assert expected == oois


def test_cve_with_metric_without_base_score():
    # A metric entry without cvssData.baseScore should not abort the normalizer.
    input_ooi = {"id": "CVE-2024-0003"}
    raw = json.dumps(
        {
            "cve": {
                "descriptions": [{"lang": "en", "value": "A CVE whose metric entry lacks a base score."}],
                "metrics": {"cvssMetricV31": [{"type": "Primary", "cvssData": {}}]},
            }
        }
    ).encode()

    oois = list(run(input_ooi, raw))

    expected = [
        NormalizerAffirmation(
            ooi=CVEFindingType(
                id="CVE-2024-0003",
                description="A CVE whose metric entry lacks a base score.",
                source="https://cve.circl.lu/cve/CVE-2024-0003",
                risk_severity=RiskLevelSeverity.UNKNOWN,
                risk_score=None,
            )
        )
    ]

    assert expected == oois


def test_cve_without_cvss():
    input_ooi = {"id": "CVE-2021-46882"}

    oois = list(run(input_ooi, get_dummy_data("inputs/cve-result-without-cvss.json")))

    expected = [
        NormalizerAffirmation(
            ooi=CVEFindingType(
                id="CVE-2021-46882",
                description="The Nested Pages plugin for WordPress is vulnerable to unauthorized loss of "
                "data due to a missing capability check on the 'reset' function in versions up to, and including, "
                "3.2.3. This makes it possible for authenticated attackers, "
                "with editor-level permissions and above, "
                "to reset plugin settings.",
                source="https://cve.circl.lu/cve/CVE-2021-46882",
                risk_severity=RiskLevelSeverity.UNKNOWN,
                risk_score=None,
            )
        )
    ]

    assert expected == oois
