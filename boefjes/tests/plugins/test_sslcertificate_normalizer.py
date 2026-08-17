from boefjes.plugins.kat_ssl_certificates.normalize import run
from tests.loading import get_dummy_data

input_ooi = {
    "object_type": "Website",
    "scan_profile": "scan_profile_type='inherited' "
    "reference=Reference('Website|internet|134.209.85.72|tcp|443|https|internet|mispo.es') level=<ScanLevel.L2: 2>",
    "primary_key": "Website|internet|134.209.85.72|tcp|443|https|internet|mispo.es",
    "ip_service": {
        "ip_port": {
            "address": {"network": {"name": "internet"}, "address": "134.209.85.72"},
            "protocol": "tcp",
            "port": "443",
        },
        "service": {"name": "https"},
    },
    "hostname": {"network": {"name": "internet"}, "name": "mispo.es"},
    "certificate": "None",
}


def test_ssl_certificates_normalizer():
    output = list(run(input_ooi, get_dummy_data("ssl-certificates.txt")))
    assert len([ooi for ooi in output if hasattr(ooi, "object_type") and ooi.object_type == "X509Certificate"]) == 3
    for ooi in output:
        if hasattr(ooi, "object_type") and ooi.object_type == "X509Certificate":
            assert ooi.valid_from != ooi.valid_until
