from bits.web_service_discovery.web_service_discovery import run

from octopoes.models.ooi.network import IPAddressV4, IPAddressV6
from octopoes.models.ooi.service import HostnameIPService, IPService


def _address(address: str) -> IPAddressV4 | IPAddressV6:
    if ":" in address:
        return IPAddressV6(address=address, network="Network|internet")
    return IPAddressV4(address=address, network="Network|internet")


def _ip_service(ip: str, port: int, service: str) -> IPService:
    return IPService(ip_port=f"IPPort|internet|{ip}|tcp|{port}", service=f"Service|{service}")


def _his(ip: str, port: int, service: str, hostname: str) -> HostnameIPService:
    return HostnameIPService(
        ip_service=f"IPService|internet|{ip}|tcp|{port}|{service}", hostname=f"Hostname|internet|{hostname}"
    )


def test_named_web_service_yields_canonical_website():
    his = _his("45.83.241.252", 443, "https", "www.baanhofman.nl")

    results = list(run(_address("45.83.241.252"), [_his_ip_service_for(his), his], {}))

    keys = sorted(str(o.primary_key) for o in results)
    assert keys == ["Website|internet|45.83.241.252|tcp|443|https|internet|www.baanhofman.nl"]
    # certificate is never set.
    assert all(o.certificate is None for o in results)


def _his_ip_service_for(his: HostnameIPService) -> IPService:
    tokenized = his.reference.tokenized
    ip_port = tokenized.ip_service.ip_port
    return IPService(
        ip_port=f"IPPort|{ip_port.address.network.name}|{ip_port.address.address}|{ip_port.protocol}|{ip_port.port}",
        service=f"Service|{tokenized.ip_service.service.name}",
    )


def test_multiple_names_yield_multiple_websites():
    ip = "45.83.241.252"
    ipservice = _ip_service(ip, 443, "https")
    his_a = _his(ip, 443, "https", "www.baanhofman.nl")
    his_b = _his(ip, 443, "https", "mta-sts.baanhofman.nl")

    results = list(run(_address(ip), [ipservice, his_a, his_b], {}))

    keys = sorted(str(o.primary_key) for o in results)
    assert keys == [
        "Website|internet|45.83.241.252|tcp|443|https|internet|mta-sts.baanhofman.nl",
        "Website|internet|45.83.241.252|tcp|443|https|internet|www.baanhofman.nl",
    ]


def test_null_sni_web_service_yields_ip_placeholder_website():
    ip = "45.83.241.252"
    ipservice = _ip_service(ip, 443, "https")

    results = list(run(_address(ip), [ipservice], {}))

    # The placeholder: hostname is the IP, the canonical key the
    # pre-migration normalizers and burpsuite's IP case write.
    assert [str(o.primary_key) for o in results] == [f"Website|internet|{ip}|tcp|443|https|internet|{ip}"]


def test_non_web_service_yields_nothing():
    ip = "2a10:3781:3ec7:1:5054:ff:fe86:d6ed"
    ipservice = _ip_service(ip, 993, "imaps")
    his = _his(ip, 993, "imaps", "mailstore.synnack.net")

    assert list(run(_address(ip), [ipservice, his], {})) == []


def test_http_service_yields_website():
    ip = "192.0.2.1"
    ipservice = _ip_service(ip, 80, "http")
    his = _his(ip, 80, "http", "plain.example.com")

    results = list(run(_address(ip), [ipservice, his], {}))

    assert [str(o.primary_key) for o in results] == [f"Website|internet|{ip}|tcp|80|http|internet|plain.example.com"]
