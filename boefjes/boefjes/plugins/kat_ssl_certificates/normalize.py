import datetime
import ipaddress
import logging
import re
from collections.abc import Iterable

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from dateutil.parser import parse

from boefjes.normalizer_models import NormalizerAffirmation, NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.certificate import (
    AlgorithmType,
    SubjectAlternativeName,
    SubjectAlternativeNameHostname,
    SubjectAlternativeNameIP,
    SubjectAlternativeNameQualifier,
    X509Certificate,
)
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, IPPort, Network, PortState, Protocol
from octopoes.models.ooi.service import IPService, Service
from octopoes.models.ooi.web import Website


def find_between(s: str, first: str, last: str) -> str:
    try:
        start = s.index(first) + len(first)
        end = s.index(last, start)
        return s[start:end]
    except ValueError:
        return ""


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    # only get the first part of certificates
    contents = find_between(raw.decode(), "Certificate chain", "Certificate chain")

    if not contents:
        return

    pk = input_ooi["primary_key"]

    # extract all certificates
    certificates, certificate_subject_alternative_names, hostnames = read_certificates(contents, Reference.from_str(pk))

    # connect server certificate to website
    if certificates:
        tokenized = Reference.from_str(pk).tokenized
        addr = ipaddress.ip_address(tokenized.ip_service.ip_port.address.address)
        network = Network(name=tokenized.ip_service.ip_port.address.network.name)
        if isinstance(addr, ipaddress.IPv4Address):
            ip_address = IPAddressV4(address=addr, network=network.reference)
        else:
            ip_address = IPAddressV6(address=addr, network=network.reference)

        ip_port = IPPort(
            address=ip_address.reference,
            protocol=Protocol(tokenized.ip_service.ip_port.protocol),
            port=int(tokenized.ip_service.ip_port.port),
            state=PortState.OPEN,
        )
        ip_service = IPService(
            ip_port=ip_port.reference, service=Service(name=tokenized.ip_service.service.name).reference
        )
        hostname = Hostname(
            network=Network(name=tokenized.hostname.network.name).reference, name=tokenized.hostname.name
        )
        website = Website(
            ip_service=ip_service.reference, hostname=hostname.reference, certificate=certificates[0].reference
        )

        # update website
        yield NormalizerAffirmation(ooi=website)

    # chain certificates together
    last_certificate = None
    for certificate in reversed(certificates):
        if last_certificate is not None:
            certificate.signed_by = last_certificate.reference

        last_certificate = certificate
        yield certificate

    # add all hostnames
    yield from hostnames

    # add all subject alternative names
    yield from certificate_subject_alternative_names


def read_certificates(
    contents: str, website_reference: Reference
) -> tuple[list[X509Certificate], list[SubjectAlternativeName], list[Hostname]]:
    # iterate through the PEM certificates and decode them
    certificates = []
    certificate_subject_alternative_names = []
    hostnames = []
    for m in re.finditer(
        r"(?<=-----BEGIN CERTIFICATE-----).*?(?=-----END CERTIFICATE-----)", contents, flags=re.DOTALL
    ):
        pem_contents = f"-----BEGIN CERTIFICATE-----{m.group()}-----END CERTIFICATE-----"

        cert = x509.load_pem_x509_certificate(pem_contents.encode(), default_backend())
        try:
            subject = cert.subject.get_attributes_for_oid(x509.OID_COMMON_NAME)[0].value
        except IndexError:
            subject = None
        issuer = cert.issuer.get_attributes_for_oid(x509.OID_ORGANIZATION_NAME)[0].value
        try:
            subject_alternative_names = [
                name.value for name in cert.extensions.get_extension_for_oid(x509.OID_SUBJECT_ALTERNATIVE_NAME).value
            ]
        except x509.ExtensionNotFound:
            subject_alternative_names = []
        valid_from = cert.not_valid_before.isoformat()
        valid_until = cert.not_valid_after.isoformat()
        pk_size = cert.public_key().key_size
        logging.info("Parsing certificate of type %s", type(cert.public_key()))
        if isinstance(cert.public_key(), rsa.RSAPublicKey):
            pk_algorithm = str(AlgorithmType.RSA)
            pk_number = cert.public_key().public_numbers().n.to_bytes(pk_size // 8, "big").hex()
        elif isinstance(cert.public_key(), ec.EllipticCurvePublicKey):
            pk_algorithm = str(AlgorithmType.ECC)
            pk_number = hex(cert.public_key().public_numbers().x) + hex(cert.public_key().public_numbers().y)
        else:
            pk_algorithm = None
            pk_number = None

        certificate = X509Certificate(
            subject=subject,
            issuer=issuer,
            valid_from=valid_from,
            valid_until=valid_until,
            pk_algorithm=pk_algorithm,
            pk_size=pk_size,
            pk_number=pk_number,
            website=website_reference,
            serial_number=cert.serial_number.to_bytes(20, "big").hex(),
            expires_in=parse(valid_until).astimezone(datetime.timezone.utc)
            - datetime.datetime.now(datetime.timezone.utc),
        )
        # todo: alt names
        certificates.append(certificate)

        network_reference = Network(name="internet").reference
        certificate_reference = certificate.reference

        for name in subject_alternative_names:
            san = None
            if isinstance(name, str):
                if "*" not in name:
                    hostname = Hostname(network=network_reference, name=name)
                    hostnames.append(hostname)
                    san = SubjectAlternativeNameHostname(hostname=hostname.reference, certificate=certificate_reference)
                else:
                    san = SubjectAlternativeNameQualifier(name=name, certificate=certificate_reference)
            elif isinstance(name, ipaddress.IPv4Address):
                address = IPAddressV4(network=network_reference, address=name)
                san = SubjectAlternativeNameIP(address=address.reference, certificate=certificate_reference)
            elif isinstance(name, ipaddress.IPv6Address):
                address = IPAddressV6(network=network_reference, address=name)
                san = SubjectAlternativeNameIP(address=address.reference, certificate=certificate_reference)
            else:
                pass  # todo: support other SANs?

            if san is not None:
                certificate_subject_alternative_names.append(san)

    return certificates, certificate_subject_alternative_names, hostnames
