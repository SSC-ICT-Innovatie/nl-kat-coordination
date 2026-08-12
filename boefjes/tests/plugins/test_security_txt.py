from boefjes.plugins.kat_security_txt_downloader.normalize import run
from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPPort, Network
from octopoes.models.ooi.service import IPService, Service
from octopoes.models.ooi.web import URL, SecurityTXT, Website
from tests.loading import get_dummy_data

input_ooi = {
    "object_type": "Website",
    "scan_profile": "scan_profile_type='declared' "
    "reference=Reference('Website|internet|192.0.2.0|tcp|443|https|internet|example.com') level=<ScanLevel.L2: 2>",
    "primary_key": "Website|internet|192.0.2.0|tcp|443|https|internet|example.com",
    "ip_service": {
        "ip_port": {
            "address": {"network": {"name": "internet"}, "address": "192.0.2.0"},
            "protocol": "tcp",
            "port": "443",
        },
        "service": {"name": "https"},
    },
    "hostname": {"network": {"name": "internet"}, "name": "example.com"},
    "certificate": "None",
}


def test_security_txt_same_website():
    oois = list(run(input_ooi, get_dummy_data("inputs/security_txt_result_same_website.json")))

    expected = []
    expected.append(URL(raw="https://example.com/.well-known/security.txt", network=Network(name="internet").reference))
    url = URL(raw="https://example.com/.well-known/security.txt", network=Network(name="internet").reference)
    expected.append(url)
    expected.append(
        SecurityTXT(
            website=Reference.from_str("Website|internet|192.0.2.0|tcp|443|https|internet|example.com"),
            url=url.reference,
            security_txt="This is the content",
            redirects_to=None,
        )
    )

    assert expected == oois


def test_security_txt_different_website():
    oois = list(run(input_ooi, get_dummy_data("inputs/security_txt_result_different_website.json")))

    expected = []
    url_original = URL(raw="https://example.com/.well-known/security.txt", network=Network(name="internet").reference)
    expected.append(url_original)
    url = URL(raw="https://www.example.com/.well-known/security.txt", network=Network(name="internet").reference)
    expected.append(url)
    expected.append(Hostname(name="www.example.com", network=Network(name="internet").reference))
    ip = IPAddressV4(address="192.0.2.1", network=Network(name="internet").reference)
    expected.append(ip)
    expected.append(Service(name="https"))
    port = IPPort(address=ip.reference, port=443, protocol="tcp")
    expected.append(port)
    ip_service = IPService(ip_port=port.reference, service=Service(name="https").reference)
    expected.append(ip_service)
    website = Website(
        ip_service=ip_service.reference,
        hostname=Hostname(name="www.example.com", network=Network(name="internet").reference).reference,
    )
    expected.append(website)
    security_txt = SecurityTXT(
        website=website.reference, url=url.reference, security_txt="This is the content", redirects_to=None
    )
    expected.append(security_txt)
    expected.append(
        SecurityTXT(
            website=Reference.from_str("Website|internet|192.0.2.0|tcp|443|https|internet|example.com"),
            url=url_original.reference,
            security_txt=None,
            redirects_to=security_txt.reference,
        )
    )
    assert expected == oois
