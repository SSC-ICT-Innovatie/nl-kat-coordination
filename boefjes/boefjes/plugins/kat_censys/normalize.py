import json
import urllib.parse
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.certificate import X509Certificate
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPPort, Network, PortState, Protocol
from octopoes.models.ooi.service import IPService, Service
from octopoes.models.ooi.software import Software, SoftwareInstance
from octopoes.models.ooi.web import HTTPHeader, HTTPResource, IPAddressHTTPURL, Website


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    results = json.loads(raw)
    ip_ooi_reference = Reference.from_str(input_ooi["primary_key"])

    network_reference = Network(name=ip_ooi_reference.tokenized.network.name).reference
    ip = results["ip"]

    if "dns" in results and "names" in results["dns"]:
        for hostname in results["dns"]["names"]:
            hostname_ooi = Hostname(name=hostname, network=network_reference)
            yield hostname_ooi

    for scan in results["services"]:
        port_nr = scan["port"]
        transport = scan["transport_protocol"].lower()

        ip_port = IPPort(
            address=ip_ooi_reference,
            protocol=Protocol(transport) if transport != "quic" else Protocol.UDP,
            port=int(port_nr),
            state=PortState("open"),
        )
        yield ip_port

        service = Service(name=scan["service_name"])
        yield service

        if "tls" in scan:
            leaf_data = scan["tls"]["certificates"]["leaf_data"]

            # X509Certificate requires valid_from/valid_until as (ISO) strings.
            # The previous code passed 0 (an int) into these fields, which raises
            # a ValidationError that aborts the whole normalizer and discards
            # every OOI already yielded for this host (ports, software, headers).
            # Only emit the certificate when Censys actually supplied validity
            # timestamps; never fabricate a placeholder, which would additionally
            # break X509Certificate.expired downstream.
            valid_from = leaf_data.get("not_before")
            valid_until = leaf_data.get("not_after")
            if valid_from and valid_until:
                # todo: link certificate properly. Currently there is no website, because it will be returned for an ip
                yield X509Certificate(
                    subject=leaf_data.get("subject_dn"),
                    issuer=leaf_data.get("issuer_dn"),
                    valid_from=valid_from,
                    valid_until=valid_until,
                    pk_algorithm=leaf_data.get("pubkey_algorithm"),
                    pk_size=leaf_data.get("pubkey_bit_size"),
                    serial_number=leaf_data["fingerprint"],
                    signed_by=None,
                )

        if "software" in scan:
            for sw in scan["software"]:
                if "product" not in sw:
                    continue
                # Keep the product name as reported (the old .upper() mangled it,
                # e.g. "nginx" -> "NGINX") and carry the CPE when Censys gives one.
                software_ooi = Software(
                    name=sw["product"], version=sw.get("version"), cpe=sw.get("uniform_resource_identifier")
                )
                yield software_ooi
                yield SoftwareInstance(ooi=ip_port.reference, software=software_ooi.reference)

        if "http" in scan and "response" in scan["http"] and "headers" in scan["http"]["response"]:
            url = urllib.parse.urlparse(scan.get("http", {}).get("request", {}).get("uri", ""))

            # Reuse the IPPort built above (with the real scanned port and state)
            # instead of rebuilding it per header with a fabricated 443/80 port
            # and Protocol[transport], which crashed on QUIC. Yield the IPService
            # and Website too — they were only ever built to be referenced.
            ip_service = IPService(ip_port=ip_port.reference, service=service.reference)
            yield ip_service

            # todo: not a valid hostname, but this needs to be fixed in the `Website` model
            hostname = Hostname(network=network_reference, name=ip)
            yield hostname

            website = Website(ip_service=ip_service.reference, hostname=hostname.reference)
            yield website

            web_url = IPAddressHTTPURL(
                network=network_reference,
                scheme=url.scheme,
                port=int(port_nr),
                path=url.path or "/",
                netloc=ip_ooi_reference,
            )
            yield web_url

            # todo: implement `HTTPResource.redirects_to` if available
            http_resource = HTTPResource(website=website.reference, web_url=web_url.reference)
            yield http_resource

            headers = scan["http"]["response"]["headers"]
            for header, values in headers.items():
                if header.startswith("_"):
                    # values starting with _ seem to be censys specific and not really part of the response headers
                    continue
                header_field = header.lower().replace("_", "-")
                # this is always a list, when there are multiple values it means it was set multiple times
                for value in values:
                    yield HTTPHeader(resource=http_resource.reference, key=header_field, value=value)
