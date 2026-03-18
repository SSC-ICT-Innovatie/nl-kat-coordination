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
