import base64
import hashlib
import re
import ssl
from collections.abc import Iterable
from datetime import UTC, datetime
from functools import cache

from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, mldsa, rsa

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.certificate import (
    SignatureVerificationStatus,
    SubjectAlternativeNameHostnameV2,
    SubjectAlternativeNameIPV2,
    SubjectAlternativeNameQualifierV2,
    TLSCertificateChain,
    X509CertificateV2,
)
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6
from octopoes.models.ooi.service import HostnameIPService

CERTIFICATE_RE = re.compile(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", flags=re.DOTALL)
HOSTNAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*\.?$")


@cache
def _trust_anchors() -> tuple[x509.Certificate, ...]:
    """The system trust store of the worker image, loaded through the
    standard SSL context (/etc/ssl/certs/ca-certificates.crt on Debian)."""
    try:
        context = ssl.create_default_context()
        return tuple(x509.load_der_x509_certificate(der) for der in context.get_ca_certs(binary_form=True))
    except OSError:
        return ()


def _issued_by(certificate: x509.Certificate, issuer: x509.Certificate) -> bool:
    """Name match plus signature verification (RFC 5280 §6 path building's
    basic step). Unsupported algorithms count as "not issued by"."""
    try:
        certificate.verify_directly_issued_by(issuer)
        return True
    except (ValueError, TypeError, InvalidSignature, UnsupportedAlgorithm):
        return False


def is_part_of_wildcard(hostname: str, wildcard: str) -> bool:
    # according to rfc2459 wildcard certificates can only be used for subdomains
    if not wildcard.startswith("*"):
        return False
    wildcard_domain = wildcard[2:].rstrip(".")
    higher_level_domain = ".".join(hostname.split(".")[1:])
    return wildcard_domain == higher_level_domain


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    """Parse openssl s_client output into certificates and certificate chains.

    A HostnameIPService input is a connection for that server name; a bare
    IPService input is a connection without a server name, whose presentation
    is valid for the null server name only.
    """
    object_type = input_ooi.get("object_type")
    if object_type not in ("IPService", "HostnameIPService"):
        return

    endpoint = Reference.from_str(input_ooi["primary_key"])
    tokenized = endpoint.tokenized
    ip_service_token = tokenized if object_type == "IPService" else tokenized.ip_service
    network_name = ip_service_token.ip_port.address.network.name
    ip_service_reference = (
        endpoint
        if object_type == "IPService"
        else Reference.from_str(
            f"IPService|{network_name}|{ip_service_token.ip_port.address.address}|"
            f"{ip_service_token.ip_port.protocol}|{ip_service_token.ip_port.port}|{ip_service_token.service.name}"
        )
    )
    input_hostname = tokenized.hostname.name if object_type == "HostnameIPService" else None

    contents = raw.decode(errors="replace")

    # Entries in wire order: (position, raw bytes, parsed certificate or None).
    entries = [
        (position, *parse_certificate(block.group().encode()))
        for position, block in enumerate(CERTIFICATE_RE.finditer(contents))
    ]
    if not entries:
        return

    parsed_entries = [(position, der, parsed) for position, der, parsed in entries if parsed is not None]

    # Every certificate in the wire order — duplicates included. The
    # graph dedups at save (same fingerprint = same primary key), and
    # a duplicated certificate is itself a malformation the walk
    # should see, not launder.
    oois: list[X509CertificateV2] = [certificate_ooi(der, parsed) for _, der, parsed in parsed_entries]
    parsed_certs: list[x509.Certificate] = [parsed for _, _, parsed in parsed_entries]

    chain = TLSCertificateChain(
        presentation_hash=presentation_hash(entries),
        presented_certificates=[ooi.reference for ooi in oois],
        **{("hostname_ip_service" if object_type == "HostnameIPService" else "ip_service"): endpoint},
    )
    yield chain

    anchors = _trust_anchors()
    if not anchors:
        # No trust store in the worker image: every assessment after
        # this is void, and the endpoint would silently look healthy.
        # An empty store is a broken image, not a scanning condition.
        raise RuntimeError("No trust anchors available: /etc/ssl/certs is empty or unreadable in the worker image")

    # The validation walks the wire order: position 0 is the leaf, each
    # following certificate certifies its predecessor (RFC 8446 4.4.2),
    # and the sequence must terminate at a root of the system trust
    # store (RFC 5280 6.1). Per the review disposition: a signature
    # mismatch on the next certificate, any garbage, and a sequence
    # that ends without reaching a root are all the same finding —
    # the chain is incomplete.
    leaf = parsed_certs[0]
    if leaf.subject == leaf.issuer and leaf.fingerprint(hashes.SHA256()).hex() not in {
        a.fingerprint(hashes.SHA256()).hex() for a in anchors
    }:
        ft = KATFindingType(id="KAT-SELF-SIGNED-CERTIFICATE")
        yield ft
        yield Finding(ooi=oois[0].reference, finding_type=ft.reference)

    now = datetime.now(UTC)
    for index, current in enumerate(parsed_certs):
        not_after = current.not_valid_after_utc
        if not_after <= now:
            ft = KATFindingType(id="KAT-CERTIFICATE-EXPIRED")
            yield ft
            yield Finding(ooi=oois[index].reference, finding_type=ft.reference)

        if index + 1 < len(parsed_certs):
            nxt = parsed_certs[index + 1]
            if not _issued_by(current, nxt):
                # The chain does not hold together: cert[index+1] does
                # not certify cert[index] — junk after the leaf, two
                # end-entity certificates, or broken order. A client
                # cannot build a path from the leaf through this
                # sequence.
                ft = KATFindingType(id="KAT-MALFORMED-CERTIFICATE-CHAIN")
                yield ft
                yield Finding(ooi=chain.reference, finding_type=ft.reference)
                break
            # The signature verified: the neighbor is the issuer.
            oois[index].signed_by = oois[index + 1].reference
        # else: the top of the presented sequence. It must be issued
        # by a root of the trust store; a top that does not verify
        # against one leaves the chain incomplete — unless the chain
        # is a lone self-signed certificate, which got its own
        # finding above and is not a chain at all.
        elif not any(_issued_by(current, anchor) for anchor in anchors) and current.subject != current.issuer:
            ft = KATFindingType(id="KAT-INCOMPLETE-CERTIFICATE-CHAIN")
            yield ft
            yield Finding(ooi=chain.reference, finding_type=ft.reference)

    # Hostname mismatch: the server name of the presentation against the
    # leaf's SAN names. A connection without a server name claims nothing
    # and is never assessed; the finding binds to the chain because a
    # HostnameIPService has a presentation per client capability variant.
    if input_hostname is not None and oois:
        hostname = input_hostname.rstrip(".")
        # The names a client may match against are the SAN's DNS names
        # (RFC 6125 6.4.4 permits a CN fallback only for legacy clients;
        # modern clients ignore the common name, so a SAN-less
        # certificate is rejected regardless of its CN). A certificate
        # without a SAN therefore never matches — matching V1's
        # behavior, where a SAN-less certificate fired the mismatch.
        try:
            names = {
                name.value.rstrip(".").lower()
                for name in leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
                if isinstance(name, x509.DNSName)
            }
        except x509.ExtensionNotFound:
            names = set()
        host = hostname.lower()
        if host not in names and not any(is_part_of_wildcard(host, wildcard) for wildcard in names):
            ft = KATFindingType(id="KAT-SSL-CERT-HOSTNAME-MISMATCH")
            yield ft
            yield Finding(ooi=chain.reference, finding_type=ft.reference)

    network = Reference.from_str(f"Network|{network_name}")

    # SANs are declared per certificate: hostnames (for DNS scheduling),
    # non-hostname names (wildcards), and IP addresses — the objects the
    # GUI and the hostname-mismatch bit consume. A HostnameIPService is
    # yielded from the presentation itself: the server at this IP claimed
    # this name; it converges with the discovery bit's DNS-derived pair
    # via the natural key.
    for index, (ooi, parsed) in enumerate(zip(oois, parsed_certs)):
        for name in subject_alternative_names(parsed):
            if isinstance(name, x509.DNSName):
                if "*" not in name.value and HOSTNAME_RE.fullmatch(name.value):
                    hostname = Hostname(name=name.value, network=network)
                    yield hostname
                    yield SubjectAlternativeNameHostnameV2(certificate=ooi.reference, hostname=hostname.reference)
                    yield HostnameIPService(ip_service=ip_service_reference, hostname=hostname.reference)
                else:
                    yield SubjectAlternativeNameQualifierV2(certificate=ooi.reference, name=name.value)
            elif isinstance(name, x509.IPAddress):
                ip_ooi = (
                    IPAddressV4(network=network, address=name.value)
                    if name.value.version == 4
                    else IPAddressV6(network=network, address=name.value)
                )
                yield SubjectAlternativeNameIPV2(certificate=ooi.reference, address=ip_ooi.reference)

    yield from oois

    # A malformed entry produces no certificate; the finding carries its
    # position and raw hash as proof.
    malformed = [(position, der) for position, der, parsed in entries if parsed is None]
    if malformed:
        finding_type = KATFindingType(id="KAT-UNPARSEABLE-CERTIFICATE")
        yield finding_type
        for position, der in malformed:
            yield Finding(
                ooi=chain.reference,
                finding_type=finding_type.reference,
                proof=f"position={position};raw_hash={hashlib.sha256(der).hexdigest()}",
            )


def parse_certificate(pem: bytes) -> tuple[bytes, x509.Certificate | None]:
    """Decode one PEM block to (raw bytes, certificate or None)."""
    try:
        parsed = x509.load_pem_x509_certificate(pem)
        return parsed.public_bytes(serialization.Encoding.DER), parsed
    except (ValueError, TypeError):
        return pem, None


def certificate_ooi(der: bytes, parsed: x509.Certificate) -> X509CertificateV2:
    return X509CertificateV2(
        fingerprint=hashlib.sha256(der).hexdigest(),
        raw=base64.b64encode(der).decode(),
        subject=parsed.subject.rfc4514_string(),
        issuer=parsed.issuer.rfc4514_string(),
        serial_number=format(parsed.serial_number, "x"),
        valid_from=parsed.not_valid_before_utc,
        valid_until=parsed.not_valid_after_utc,
        pk_algorithm=pk_algorithm(parsed.public_key()),
        signed_by=None,
    )


def presentation_hash(entries: list[tuple[int, bytes, x509.Certificate | None]]) -> str:
    """SHA-256 over length-prefixed SHA-256 hashes of every raw presented
    entry, in wire order — including entries that failed to parse."""
    digest = hashlib.sha256()
    for _position, der, _parsed in sorted(entries):
        h = hashlib.sha256(der).hexdigest().encode()
        digest.update(len(h).to_bytes(4, "big"))
        digest.update(h)
    return digest.hexdigest()


def pk_algorithm(public_key) -> str:
    """Free-string algorithm family. Sizes are deliberately absent: they are
    only comparable within a family and are derivable from the raw DER."""
    if isinstance(public_key, rsa.RSAPublicKey):
        return "RSA"
    if isinstance(public_key, ec.EllipticCurvePublicKey):
        return f"EC {public_key.curve.name}"
    if isinstance(public_key, ed25519.Ed25519PublicKey):
        return "Ed25519"
    if isinstance(public_key, ed448.Ed448PublicKey):
        return "Ed448"
    if isinstance(public_key, mldsa.MLDSA44PublicKey | mldsa.MLDSA65PublicKey | mldsa.MLDSA87PublicKey):
        return type(public_key).__name__.removesuffix("PublicKey").upper().replace("MLDSA", "ML-DSA-")
    return type(public_key).__name__


def subject_alternative_names(parsed: x509.Certificate) -> list:
    try:
        return list(parsed.extensions.get_extension_for_class(x509.SubjectAlternativeName).value)
    except x509.ExtensionNotFound:
        return []


def verify_certificate_signature(
    certificate: x509.Certificate, issuer: x509.Certificate
) -> SignatureVerificationStatus:
    """Verify the certificate's signature with the issuer's public key. The
    caller should check the issuer claim first, and only attempt
    cryptographic verification for candidates whose subject matches."""
    try:
        # Keep mismatched certificates out of the candidate relationships.
        if certificate.issuer != issuer.subject:
            return SignatureVerificationStatus.ISSUER_NAME_MISMATCH

        issuer_public_key = issuer.public_key()

        if isinstance(issuer_public_key, rsa.RSAPublicKey):
            issuer_public_key.verify(
                certificate.signature,
                certificate.tbs_certificate_bytes,
                certificate.signature_algorithm_parameters,
                certificate.signature_hash_algorithm,
            )
        elif isinstance(issuer_public_key, ec.EllipticCurvePublicKey):
            issuer_public_key.verify(
                certificate.signature, certificate.tbs_certificate_bytes, ec.ECDSA(certificate.signature_hash_algorithm)
            )
        elif isinstance(
            issuer_public_key,
            ed25519.Ed25519PublicKey
            | ed448.Ed448PublicKey
            | mldsa.MLDSA44PublicKey
            | mldsa.MLDSA65PublicKey
            | mldsa.MLDSA87PublicKey,
        ):
            issuer_public_key.verify(certificate.signature, certificate.tbs_certificate_bytes)
        else:
            return SignatureVerificationStatus.UNSUPPORTED_KEY_TYPE

    except InvalidSignature:
        return SignatureVerificationStatus.INVALID_SIGNATURE
    except UnsupportedAlgorithm:
        return SignatureVerificationStatus.UNSUPPORTED_ALGORITHM
    except (TypeError, ValueError):
        return SignatureVerificationStatus.INVALID_PARAMETERS

    return SignatureVerificationStatus.VERIFIED
