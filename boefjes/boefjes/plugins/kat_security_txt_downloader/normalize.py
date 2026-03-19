import ipaddress
import json
from collections.abc import Iterable
from urllib.parse import urlparse

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, IPPort, Network
from octopoes.models.ooi.service import IPService, Service
from octopoes.models.ooi.web import URL, SecurityTXT, Website


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    results = json.loads(raw)
    website_original = Reference.from_str(input_ooi["primary_key"])

    for path, details in results.items():
        if details["content"] is None:
            continue
        url_original = URL(
            raw=f'{input_ooi["ip_service"]["service"]["name"]}://{input_ooi["hostname"]["name"]}/{path}',
            network=Network(name=input_ooi["hostname"]["network"]["name"]).reference,
        )
        yield url_original
        url = URL(raw=details["url"], network=Network(name=input_ooi["hostname"]["network"]["name"]).reference)
        yield url
        url_parts = urlparse(details["url"])
        # we need to check if the website of the response is the same as the input website
        if (
            url_parts.scheme == input_ooi["ip_service"]["service"]["name"]
            and url_parts.netloc == input_ooi["hostname"]["name"]
            and details["ip"] == input_ooi["ip_service"]["ip_port"]["address"]["address"]
        ):
            security_txt = SecurityTXT(
                website=website_original, url=url.reference, security_txt=details["content"], redirects_to=None
            )
            yield security_txt
        # otherwise we need to create a new website complete with hostname and ip
        else:
            hostname = Hostname(
                name=url_parts.netloc, network=Network(name=input_ooi["hostname"]["network"]["name"]).reference
            )
            yield hostname
            addr = ipaddress.ip_address(details["ip"])
            if addr.version == 6:
                ip_address = IPAddressV6(
                    address=details["ip"], network=Network(name=input_ooi["hostname"]["network"]["name"]).reference
                )
            else:
                ip_address = IPAddressV4(
                    address=details["ip"], network=Network(name=input_ooi["hostname"]["network"]["name"]).reference
                )
            yield ip_address
            # check scheme for service and ipport
            if url_parts.scheme == "https":
                service = Service(name="https")
                yield service
                ip_port = IPPort(address=ip_address.reference, port=443, protocol="tcp")
                yield ip_port
                ip_service = IPService(ip_port=ip_port.reference, service=service.reference)
                yield ip_service
            else:
                service = Service(name="http")
                yield service
                ip_port = IPPort(address=ip_address.reference, port=80, protocol="tcp")
                yield ip_port
                ip_service = IPService(ip_port=ip_port.reference, service=service.reference)
                yield ip_service

            website = Website(hostname=hostname.reference, ip_service=ip_service.reference)
            yield website
            security_txt = SecurityTXT(
                website=website.reference, url=url.reference, security_txt=details["content"], redirects_to=None
            )
            yield security_txt
            # the original securitytxt redirects to this one
            security_txt_original = SecurityTXT(
                website=website_original,
                url=url_original.reference,
                redirects_to=security_txt.reference,
                security_txt=None,
            )
            yield security_txt_original
