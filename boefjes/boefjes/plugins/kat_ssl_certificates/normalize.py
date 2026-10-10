import datetime
import ipaddress
import logging
import re
from collections.abc import Iterable

from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, rsa
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


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    contents = raw.decode(errors="replace")

    if "-----BEGIN CERTIFICATE-----" not in contents:
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

    certificates, certificate_subject_alternative_names, hostnames = read_certificates(contents, Reference.from_str(pk))
    # Yield certificates after their chain relationships have been resolved.
    yield from certificates

    # add all hostnames
    yield from hostnames

    # add all subject alternative names
    yield from certificate_subject_alternative_names


def _certificate_is_signed_by(certificate: x509.Certificate, issuer: x509.Certificate) -> bool:
    if certificate.issuer != issuer.subject:
        return False

    try:
        issuer_public_key = issuer.public_key()

        if isinstance(issuer_public_key, rsa.RSAPublicKey | ec.EllipticCurvePublicKey):
            issuer_public_key.verify(
                certificate.signature,
                certificate.tbs_certificate_bytes,
                certificate.signature_algorithm_parameters,
                certificate.signature_hash_algorithm,
            )
        elif isinstance(issuer_public_key, ed25519.Ed25519PublicKey | ed448.Ed448PublicKey):
            issuer_public_key.verify(certificate.signature, certificate.tbs_certificate_bytes)
        else:
            return False

    except (InvalidSignature, UnsupportedAlgorithm, ValueError):
        return False

    return True


def read_certificates(
    contents: str, website_reference: Reference
) -> tuple[list[X509Certificate], list[SubjectAlternativeName], list[Hostname]]:
    # iterate through the PEM certificates and decode them
    certificates = []
    parsed_certificates = []
    certificate_subject_alternative_names = []
    hostnames = []
    seen_certificates = set()

    for m in re.finditer(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", contents, flags=re.DOTALL):
        pem_contents = m.group()

        try:
            cert = x509.load_pem_x509_certificate(pem_contents.encode(), default_backend())
        except ValueError:
            logging.warning("Unable to parse PEM certificate, skipping it")
            continue

        certificate_der = cert.public_bytes(serialization.Encoding.DER)

        if certificate_der in seen_certificates:
            continue

        seen_certificates.add(certificate_der)

        try:
            subject = cert.subject.get_attributes_for_oid(x509.OID_COMMON_NAME)[0].value
        except IndexError:
            subject = None

        # get the issuer organization name, if available
        issuer_attributes = cert.issuer.get_attributes_for_oid(x509.OID_ORGANIZATION_NAME)

        # Catch cases where no OrganizationName is present in the issuer field
        issuer = issuer_attributes[0].value if issuer_attributes else None

        try:
            subject_alternative_names = list(
                cert.extensions.get_extension_for_oid(x509.OID_SUBJECT_ALTERNATIVE_NAME).value
            )
        except x509.ExtensionNotFound:
            subject_alternative_names = []

        valid_from = cert.not_valid_before_utc.isoformat()
        valid_until = cert.not_valid_after_utc.isoformat()

        public_key = cert.public_key()

        logging.info("Parsing certificate of type %s", type(public_key))

        if isinstance(public_key, rsa.RSAPublicKey):
            pk_algorithm = str(AlgorithmType.RSA)
            pk_size = public_key.key_size
            pk_number = public_key.public_numbers().n.to_bytes(pk_size // 8, "big").hex()
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            pk_algorithm = str(AlgorithmType.ECC)
            pk_size = public_key.key_size
            pk_number = hex(public_key.public_numbers().x) + hex(public_key.public_numbers().y)
        elif isinstance(public_key, ed25519.Ed25519PublicKey | ed448.Ed448PublicKey):
            pk_algorithm = str(AlgorithmType.EDDSA)
            pk_size = None
            pk_number = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
        else:
            pk_algorithm = None
            pk_size = None
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

        certificates.append(certificate)
        parsed_certificates.append((certificate, cert))

        # Process the subject alternative names for this certificate on the Network object it belongs to.
        network_reference = Network(name=website_reference.tokenized.hostname.network.name).reference
        certificate_reference = certificate.reference

        for name in subject_alternative_names:
            san = None

            if isinstance(name, x509.DNSName):
                if "*" not in name.value:
                    hostname = Hostname(network=network_reference, name=name.value)
                    hostnames.append(hostname)

                    san = SubjectAlternativeNameHostname(hostname=hostname.reference, certificate=certificate_reference)
                else:
                    san = SubjectAlternativeNameQualifier(name=name.value, certificate=certificate_reference)

            elif isinstance(name, x509.IPAddress):
                if isinstance(name.value, ipaddress.IPv4Address):
                    address = IPAddressV4(network=network_reference, address=name.value)
                else:
                    address = IPAddressV6(network=network_reference, address=name.value)

                san = SubjectAlternativeNameIP(address=address.reference, certificate=certificate_reference)

            if san is not None:
                certificate_subject_alternative_names.append(san)

    # Link certificates using the actual issuer/subject relationship
    # instead of relying on the order returned by OpenSSL.
    for certificate, cert in parsed_certificates:
        if cert.issuer == cert.subject:
            continue

        issuer_certificate = next(
            (
                candidate
                for candidate, candidate_cert in parsed_certificates
                if _certificate_is_signed_by(cert, candidate_cert)
            ),
            None,
        )

        if issuer_certificate is not None:
            certificate.signed_by = issuer_certificate.reference

    return certificates, certificate_subject_alternative_names, hostnames
