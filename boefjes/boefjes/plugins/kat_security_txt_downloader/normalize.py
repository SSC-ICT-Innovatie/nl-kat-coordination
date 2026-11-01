import ipaddress
import json
from collections.abc import Iterable
from urllib.parse import urlparse

import validators

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.email import EmailAddress, EmailAddressInstance
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, IPPort, Network
from octopoes.models.ooi.service import IPService, Service
from octopoes.models.ooi.web import URL, SecurityTXT, Website

URL_FIELDS = {"hiring", "policy", "acknowledgments", "canonical"}


def parse_securitytxt(content: str) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}

    for line in content.splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()

        fields.setdefault(key, []).append(value)

    return fields


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    results = json.loads(raw)
    website_original = Reference.from_str(input_ooi["primary_key"])
    network_ref = Network(name=input_ooi["hostname"]["network"]["name"]).reference

    for path, details in results.items():
        if details["content"] is None:
            continue
        url_original = URL(
            raw=f'{input_ooi["ip_service"]["service"]["name"]}://{input_ooi["hostname"]["name"]}/{path}',
            network=network_ref,
        )
        yield url_original
        url = URL(raw=details["url"], network=network_ref)
        yield url
        url_parts = urlparse(details["url"])
        # we need to check if the website of the response is the same as the input website
        if (
            url_parts.scheme == input_ooi["ip_service"]["service"]["name"]
            and url_parts.hostname == input_ooi["hostname"]["name"]
            and details["ip"] == input_ooi["ip_service"]["ip_port"]["address"]["address"]
        ):
            security_txt = SecurityTXT(
                website=website_original, url=url.reference, security_txt=details["content"], redirects_to=None
            )
            yield security_txt
        # otherwise we need to create a new website complete with hostname and ip
        else:
            hostname = Hostname(name=url_parts.hostname, network=network_ref)
            yield hostname
            addr = ipaddress.ip_address(details["ip"])
            if addr.version == 6:
                ip_address = IPAddressV6(address=details["ip"], network=network_ref)
            else:
                ip_address = IPAddressV4(address=details["ip"], network=network_ref)
            yield ip_address
            # check scheme for service and ipport
            if url_parts.scheme == "https":
                service = Service(name="https")
                yield service
            else:
                service = Service(name="http")
                yield service

            port = url_parts.port or (443 if url_parts.scheme == "https" else 80)
            ip_port = IPPort(address=ip_address.reference, port=port, protocol="tcp")
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
        # lookup some other fields
        fields = parse_securitytxt(details["content"])

        for contact in fields.get("contact", []):
            if contact.lower().startswith("mailto:"):
                email = contact[7:].split("?")[0].strip()

                if not validators.email(email):
                    continue

                localpart, domain = email.lower().split("@", 1)

                domain_ooi = Hostname(name=domain.strip(), network=network_ref)
                yield domain_ooi
                emailaddress = EmailAddress(localpart=localpart, domain=domain_ooi.reference)
                yield emailaddress
                yield EmailAddressInstance(emailaddress=emailaddress.reference, location=security_txt.reference)

        seen_urls = set()

        for field in URL_FIELDS:
            for value in fields.get(field, []):
                value = value.strip()

                if value in seen_urls:
                    continue
                seen_urls.add(value)

                parsed = urlparse(value)
                if not parsed.scheme or not parsed.netloc:
                    continue

                yield URL(raw=value, network=network_ref)
