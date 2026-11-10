import base64
import hashlib
import re
import ssl
from collections.abc import Iterable
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


def _anchored(
    certificate: x509.Certificate, presented: list[x509.Certificate], anchor_fingerprints: set[bytes], visiting: tuple
) -> bool:
    """Whether a client can reach a trust anchor from this certificate using
    the presentation and the trust store. A certificate is anchored when it
    is a trust anchor, verifies against one, or verifies against another
    presented certificate that is itself anchored (recursively, with cycle
    protection for cross-signed intermediates). Issuing itself does not
    count: that is what makes a self-signed leaf incomplete."""
    if certificate.fingerprint(hashes.SHA256()) in anchor_fingerprints:
        return True
    if any(_issued_by(certificate, anchor) for anchor in _trust_anchors()):
        return True
    return any(
        other is not certificate
        and other not in visiting
        and _issued_by(certificate, other)
        and _anchored(other, presented, anchor_fingerprints, visiting + (certificate,))
        for other in presented
    )


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

    # Content-addressed certificates: identical certificates dedup via the
    # fingerprint key; every presented position keeps its own reference.
    certificates: dict[str, X509CertificateV2] = {}
    parsed_by_ooi: dict[str, x509.Certificate] = {}
    for _position, der, parsed in parsed_entries:
        fingerprint = hashlib.sha256(der).hexdigest()
        if fingerprint not in certificates:
            certificates[fingerprint] = certificate_ooi(der, parsed)
            parsed_by_ooi[fingerprint] = parsed

    # Issuer relationships within this presentation: verify each candidate
    # and set signed_by on the first verified issuer in wire order.
    pairs = [(certificates[f], parsed_by_ooi[f]) for f in certificates]
    ordered_references = [ooi.reference for ooi, _ in pairs]
    for ooi, parsed in pairs:
        for candidate_ooi, candidate_parsed in pairs:
            if candidate_ooi is ooi:
                continue
            if verify_certificate_signature(parsed, candidate_parsed) == SignatureVerificationStatus.VERIFIED:
                ooi.signed_by = candidate_ooi.reference
                break

    chain = TLSCertificateChain(
        presentation_hash=presentation_hash(entries),
        presented_certificates=ordered_references,
        **{("hostname_ip_service" if object_type == "HostnameIPService" else "ip_service"): endpoint},
    )
    yield chain

    anchors = _trust_anchors()
    if anchors:
        anchor_fingerprints = {anchor.fingerprint(hashes.SHA256()) for anchor in anchors}
        parsed_certs = [parsed for _, parsed in pairs]

        # The leaf is the certificate that issues nobody else in the
        # presentation. A self-signed leaf gets its own finding (one meaning
        # per type) and is not counted as an incomplete chain: it is not a
        # CA-issued chain missing something, it is not a chain at all.
        leaf_pairs = [
            (ooi, parsed)
            for ooi, parsed in pairs
            if not any(_issued_by(other_parsed, parsed) for other_ooi, other_parsed in pairs if other_ooi is not ooi)
        ]
        if len(leaf_pairs) == 1:
            leaf_ooi, leaf = leaf_pairs[0]
            assert leaf_ooi.fingerprint is not None  # every parsed entry carries its computed fingerprint
            if leaf.subject == leaf.issuer and leaf.fingerprint(hashes.SHA256()) not in anchor_fingerprints:
                ft = KATFindingType(id="KAT-SELF-SIGNED-CERTIFICATE")
                yield ft
                yield Finding(
                    ooi=chain.reference,
                    finding_type=ft.reference,
                    description=f"The certificate presented for this service is self-signed: "
                    f"{leaf_ooi.fingerprint[:16]} (subject {leaf.subject.rfc4514_string()}).",
                )
            elif not _anchored(leaf, parsed_certs, anchor_fingerprints, ()):
                # Only the leaf's path to a root matters: extra presented
                # certificates (cross-signs, alternate chains) are means,
                # not obligations. A client validates the leaf; an
                # unanchored cross-sign does not make the presentation
                # incomplete (the classic LE long-chain shape).
                ft = KATFindingType(id="KAT-INCOMPLETE-CERTIFICATE-CHAIN")
                yield ft
                yield Finding(
                    ooi=chain.reference,
                    finding_type=ft.reference,
                    description="The presented certificate chain does not verifiably terminate at a trusted "
                    f"root for: {leaf.subject.rfc4514_string()} ({leaf_ooi.fingerprint[:16]}).",
                )

    # Hostname mismatch: the server name of the presentation against the
    # leaf's SAN names. A connection without a server name claims nothing
    # and is never assessed; the finding binds to the chain because a
    # HostnameIPService has a presentation per client capability variant.
    if input_hostname is not None and pairs:
        hostname = input_hostname.rstrip(".")
        # The leaf is the certificate that issues nobody else in the
        # presentation.
        leaf_pairs = [
            (ooi, parsed)
            for ooi, parsed in pairs
            if not any(_issued_by(other_parsed, parsed) for other_ooi, other_parsed in pairs if other_ooi is not ooi)
        ]
        if len(leaf_pairs) == 1:
            leaf_ooi, leaf = leaf_pairs[0]
            assert leaf_ooi.fingerprint is not None  # every parsed entry carries its computed fingerprint
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
                yield Finding(
                    ooi=chain.reference,
                    finding_type=ft.reference,
                    description=f"The hostname {hostname} does not match the certificate "
                    f"{leaf_ooi.fingerprint[:16]} presented for it (names: {', '.join(sorted(names)) or 'none'}).",
                )

    network = Reference.from_str(f"Network|{network_name}")

    # SANs are declared per certificate: hostnames (for DNS scheduling),
    # non-hostname names (wildcards), and IP addresses — the objects the
    # GUI and the hostname-mismatch bit consume. A HostnameIPService is
    # yielded from the presentation itself: the server at this IP claimed
    # this name; it converges with the discovery bit's DNS-derived pair
    # via the natural key.
    for ooi, parsed in pairs:
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

    yield from certificates.values()

    # A malformed entry produces no certificate; the finding carries its
    # position and raw hash as proof.
    malformed = [(position, der) for position, der, parsed in entries if parsed is None]
    if malformed:
        finding_type = KATFindingType(id="KAT-UNPARSEABLE-CERTIFICATE")
        yield finding_type
        for position, der in malformed:
            yield Finding(
                finding_type=finding_type.reference,
                ooi=chain.reference,
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
