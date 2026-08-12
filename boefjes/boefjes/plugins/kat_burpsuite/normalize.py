import base64
from collections.abc import Iterable
from ipaddress import IPv4Address, IPv6Address, ip_address
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from defusedxml import minidom

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import CAPECFindingType, CVEFindingType, CWEFindingType, Finding
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, IPPort, Network, Protocol
from octopoes.models.ooi.service import IPService, Service
from octopoes.models.ooi.web import URL, HostnameHTTPURL, HTTPHeader, HTTPResource, IPAddressHTTPURL, WebScheme, Website


def find_network(data: dict) -> dict:
    if "network" in data:
        return data["network"]
    for key, value in data.items():
        if isinstance(value, dict):
            result = find_network(value)
            if result is not None:
                return result
    # Return internet if network is not found
    return {"name": "internet"}


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    parser = minidom.parseString(raw.decode("UTF-8"))

    network = Network(name=find_network(input_ooi).get("name", "internet"))

    tcp_protocol = Protocol.TCP

    # TODO use timestamp for sample to setup new OOI's
    #  with parser.getElementsByTagName('issues').attributes['exportTime'].value

    for issue in parser.getElementsByTagName("issue"):
        host_element = issue.getElementsByTagName("host")[0]
        host = host_element.firstChild.nodeValue

        ip = ip_address(host_element.attributes["ip"].value)
        path = issue.getElementsByTagName("path")[0].firstChild.nodeValue

        yield URL(network=network.reference, raw=f"{host}{path}")

        url = urlparse(f"{host}{path}")

        hostname = None
        # we might be dealing with a request to an IP-address
        if url.netloc != ip:
            hostname = Hostname(name=url.netloc, network=network.reference)
            yield hostname

        port = 443 if url.scheme == "https" else 80

        address = ip_address(ip)
        if isinstance(address, IPv4Address):
            ip = IPAddressV4(address=address, network=network.reference)
        elif isinstance(address, IPv6Address):
            ip = IPAddressV6(address=address, network=network.reference)

        ip_port = IPPort(address=ip.reference, protocol=tcp_protocol, port=port)
        yield ip_port

        service = Service(name=url.scheme)
        yield service

        ip_service = IPService(ip_port=ip_port.reference, service=service.reference)
        yield ip_service

        http_resource = None
        if hostname is not None:
            http_url = HostnameHTTPURL(
                network=network.reference,
                scheme=WebScheme(url.scheme),
                port=port,
                path=url.path,
                netloc=hostname.reference,
            )
            website = Website(hostname=hostname.reference, ip_service=ip_service.reference)
            yield website
            http_resource = HTTPResource(website=website.reference, web_url=http_url.reference)
            yield http_resource
        else:
            http_url = IPAddressHTTPURL(
                network=network.reference, scheme=WebScheme(url.scheme), port=port, path=url.path, netloc=url.netloc
            )

        if issue.getElementsByTagName("vulnerabilityClassifications"):
            vulnerability_classifications = issue.getElementsByTagName("vulnerabilityClassifications")[
                0
            ].firstChild.nodeValue

            soup = BeautifulSoup(vulnerability_classifications)
            for link_element in soup.find_all("a"):
                description = link_element.string.split(":")
                if description[0].startswith("CWE"):
                    finding_type = CWEFindingType(id=description[0])
                elif description[0].startswith("CAPEC"):
                    finding_type = CAPECFindingType(id=description[0])
                elif description[0].startswith("CVE"):
                    finding_type = CVEFindingType(id=description[0])
                else:
                    continue
                yield finding_type
                f = Finding(finding_type=finding_type.reference, ooi=http_url.reference, description=description[1])
                yield f

        if issue.getElementsByTagName("response"):
            response = issue.getElementsByTagName("response")[0]
            # decode the response if its encoded
            if response.attributes["base64"].value == "true":
                response = base64.b64decode(response.firstChild.nodeValue).decode()
            else:
                response = response.firstChild.nodeValue.decode()

            # currently we only support websites with hostnames as netloc, therefore we should only
            # add these headers if the resource exists
            if http_resource is not None:
                headers = response.split("\r\n\r\n")[0].split("\n\n")[0]
                for header in headers.splitlines():
                    header = header.split(":", 2)
                    # remove headers without key value structure
                    if len(header) == 2:
                        yield HTTPHeader(resource=http_resource.reference, key=header[0], value=header[1])
