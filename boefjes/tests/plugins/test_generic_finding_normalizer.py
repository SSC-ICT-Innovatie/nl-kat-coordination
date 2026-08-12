from boefjes.plugins.kat_finding_normalizer.normalize import run
from octopoes.models import Reference
from octopoes.models.ooi.findings import KATFindingType
from octopoes.models.types import CVEFindingType, Finding


def test_single():
    input_ooi = {"primary_key": "Network|internet"}

    oois = list(run(input_ooi, b"CVE-2021-00000"))

    expected = [
        CVEFindingType(id="CVE-2021-00000"),
        Finding(
            finding_type=CVEFindingType(id="CVE-2021-00000").reference,
            ooi=Reference.from_str("Network|internet"),
            description="CVE-2021-00000 is found on this OOI",
        ),
    ]

    assert expected == oois


def test_multiple():
    input_ooi = {"primary_key": "Network|internet"}

    oois = list(run(input_ooi, b"CVE-2021-00000, KAT-MOCK-FINDING"))

    expected = [
        CVEFindingType(id="CVE-2021-00000"),
        Finding(
            finding_type=CVEFindingType(id="CVE-2021-00000").reference,
            ooi=Reference.from_str("Network|internet"),
            description="CVE-2021-00000 is found on this OOI",
        ),
        KATFindingType(id="KAT-MOCK-FINDING"),
        Finding(
            finding_type=KATFindingType(id="KAT-MOCK-FINDING").reference,
            ooi=Reference.from_str("Network|internet"),
            description="KAT-MOCK-FINDING is found on this OOI",
        ),
    ]

    assert expected == oois
