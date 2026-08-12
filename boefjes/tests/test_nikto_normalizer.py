from unittest import TestCase

from boefjes.plugins.kat_nikto.normalize import run
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.software import Software, SoftwareInstance
from tests.loading import get_dummy_data


class NiktoNormalizerTest(TestCase):
    def test_outdated_and_legacy_missing_header(self):
        # The legacy fixture (Nikto 2.5-era message format) exercises two branches:
        # - id 600575 → outdated software
        # - id 999103 → missing security header, with the "The <Header> header is not set." wording
        # The old-format regex should still extract the header name.
        input_ooi = {"primary_key": "Hostname|internet|example.com"}
        ooi_ref = Reference.from_str(input_ooi["primary_key"])

        oois = list(run(input_ooi, get_dummy_data("raw/nikto-example.com.json")))

        software = Software(name="nginx", version="1.18.0")
        software_instance = SoftwareInstance(ooi=ooi_ref, software=software.reference)
        outdated_type = KATFindingType(id="KAT-OUTDATED-SOFTWARE")
        outdated_finding = Finding(
            finding_type=outdated_type.reference,
            ooi=software_instance.reference,
            description="nginx/1.18.0 appears to be outdated (current is at least 1.25.3).",
        )
        missing_header_type = KATFindingType(id="KAT-NO-X-CONTENT-TYPE-OPTIONS")
        missing_header_finding = Finding(
            finding_type=missing_header_type.reference,
            ooi=ooi_ref,
            description=(
                "The X-Content-Type-Options header is not set. This could allow the user agent "
                "to render the content of the site in a different fashion to the MIME type."
            ),
        )

        expected = [
            software,
            software_instance,
            outdated_type,
            outdated_finding,
            missing_header_type,
            missing_header_finding,
        ]

        self.assertEqual(expected, oois)

    def test_unmapped_id_yields_generic_finding(self):
        # Even an unmapped id (here "0": connection failure) is surfaced as a generic finding
        # rather than silently dropped — fixes the symptom reported by Kennisnet.
        input_ooi = {"primary_key": "Hostname|internet|non-existing.com"}
        ooi_ref = Reference.from_str(input_ooi["primary_key"])

        oois = list(run(input_ooi, get_dummy_data("raw/nikto-non-existing.com.json")))

        self.assertEqual(2, len(oois))
        self.assertEqual("KATFindingType", oois[0].object_type)
        self.assertEqual("KAT-NIKTO-FINDING", oois[0].id)
        self.assertEqual("Finding", oois[1].object_type)
        self.assertEqual(ooi_ref, oois[1].ooi)

    def test_nikto_2_6_full_coverage(self):
        # Fixture captured from a real `nikto 2.6.0` run against apache.dvwa.cloud with
        # Tuning=3b. Asserts that every vulnerability id in the fixture produces a
        # finding — this is the exact regression reported by Kennisnet.
        input_ooi = {"primary_key": "Website|internet|192.0.2.10|tcp|443|https|internet|apache.dvwa.cloud"}

        oois = list(run(input_ooi, get_dummy_data("raw/nikto-apache.dvwa.cloud.json")))

        finding_type_ids = {o.id for o in oois if o.object_type == "KATFindingType"}
        findings = [o for o in oois if o.object_type == "Finding"]
        software = [o for o in oois if o.object_type == "Software"]

        # 013587 → specific mapped type for x-content-type-options (new Nikto 2.6 message format)
        self.assertIn("KAT-NO-X-CONTENT-TYPE-OPTIONS", finding_type_ids)
        # 600050 → outdated software
        self.assertIn("KAT-OUTDATED-SOFTWARE", finding_type_ids)
        # 999992 → wildcard certificate
        self.assertIn("KAT-WILDCARD-CERTIFICATE", finding_type_ids)
        # 999990 with TRACE in msg AND 000434 both map to TRACE method finding
        self.assertIn("KAT-HTTP-TRACE-METHOD", finding_type_ids)
        # 003584 → default file exposed
        self.assertIn("KAT-EXPOSED-DEFAULT-FILE", finding_type_ids)
        # 999986 → banner disclosure, yields a Software + generic catch-all finding
        self.assertIn("KAT-NIKTO-FINDING", finding_type_ids)
        self.assertTrue(any(s.name == "Apache" and s.version == "2.4.49" for s in software))

        # Every vulnerability in the fixture should surface exactly one Finding (seven in total).
        self.assertEqual(7, len(findings))
