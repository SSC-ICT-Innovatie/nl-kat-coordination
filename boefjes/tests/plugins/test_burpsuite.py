import base64

from boefjes.plugins.kat_burpsuite.normalize import run
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import Finding
from octopoes.models.ooi.network import IPAddressV4, Network
from octopoes.models.ooi.web import IPAddressHTTPURL, WebScheme

RESPONSE = base64.b64encode(b"HTTP/1.1 200 OK\r\nServer: nginx\r\n\r\nbody").decode()


def burp_export(host: str, ip: str) -> bytes:
    return f"""<?xml version="1.0"?><issues><issue><host ip="{ip}">{host}</host><path>/login</path>
<vulnerabilityClassifications><![CDATA[<a href="x">CWE-79: XSS</a>]]></vulnerabilityClassifications>
<response base64="true">{RESPONSE}</response></issue></issues>""".encode()


def test_burpsuite_ip_url_finding_is_attached_to_ip_address_url():
    output = list(run({"network": {"name": "internet"}}, burp_export("http://93.184.215.14", "93.184.215.14")))

    assert not [o for o in output if isinstance(o, Hostname)]
    ip = next(o for o in output if isinstance(o, IPAddressV4))
    url = IPAddressHTTPURL(
        network=Network(name="internet").reference, scheme=WebScheme.HTTP, port=80, path="/login", netloc=ip.reference
    )
    finding = next(o for o in output if isinstance(o, Finding))
    assert finding.ooi == url.reference


def test_burpsuite_hostname_url_yields_hostname_and_ip():
    output = list(run({"network": {"name": "internet"}}, burp_export("https://example.org", "93.184.215.14")))

    assert [o.name for o in output if isinstance(o, Hostname)] == ["example.org"]
    assert [str(o.address) for o in output if isinstance(o, IPAddressV4)] == ["93.184.215.14"]
