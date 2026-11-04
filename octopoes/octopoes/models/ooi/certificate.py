from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import Enum, StrEnum
from typing import Literal

from octopoes.models import OOI, Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddress
from octopoes.models.ooi.service import HostnameIPService, IPService
from octopoes.models.persistence import ReferenceField


class SignatureVerificationStatus(StrEnum):
    VERIFIED = "verified"
    ISSUER_NAME_MISMATCH = "issuer_name_mismatch"  # The issuer distinguished name does not match.
    INVALID_SIGNATURE = "invalid_signature"  # The signature is invalid.
    UNSUPPORTED_ALGORITHM = "unsupported_algorithm"  # The verification algorithm is unsupported.
    INVALID_PARAMETERS = "invalid_parameters"  # The certificate parameters are invalid.
    UNSUPPORTED_KEY_TYPE = "unsupported_key_type"  # The issuer uses an unsupported public-key type.


class AlgorithmType(Enum):
    """Represents the Algorithm Type from TLS certificates.

    Possible values
    ---------------
    RSA, ECC, EdDSA
    """

    RSA = "RSA"
    ECC = "ECC"
    EDDSA = "EdDSA"


class X509Certificate(OOI):
    """Represents X509 certificates.

    Possible values
    ---------------
    Subject, issuer, valid from, valid intil, PK Algorithm, PK size, PK number, serial number,
    expires in
    """

    object_type: Literal["X509Certificate"] = "X509Certificate"

    subject: str | None = None
    issuer: str | None = None
    issuer_distinguished_name: str | None = None
    valid_from: str
    valid_until: str
    pk_algorithm: str | None = None
    pk_size: int | None = None
    pk_number: str | None = None
    signed_by: Reference | None = ReferenceField(
        "X509Certificate", max_issue_scan_level=1, max_inherit_scan_level=0, default=None
    )
    serial_number: str
    expires_in: timedelta | None = None

    _natural_key_attrs = ["issuer", "serial_number"]

    @property
    def expired(self):
        valid_until = datetime.fromisoformat(self.valid_until.replace("Z", "+00:00"))

        # Treat naive timestamps as UTC
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=UTC)

        return datetime.now(UTC) > valid_until

    _reverse_relation_names = {"signed_by": "signed_certificates"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"{reference.tokenized.issuer} ({reference.tokenized.serial_number})"


class CertificateIssuerCandidate(OOI):
    """A certificate whose subject matches another certificate's claimed issuer.

    Verification status records whether the candidate's public key
    successfully verifies the certificate's signature.
    """

    object_type: Literal["CertificateIssuerCandidate"] = "CertificateIssuerCandidate"

    certificate: Reference = ReferenceField(X509Certificate, max_issue_scan_level=1, max_inherit_scan_level=0)
    candidate_issuer: Reference = ReferenceField(X509Certificate, max_issue_scan_level=1, max_inherit_scan_level=0)

    verification_status: SignatureVerificationStatus

    _natural_key_attrs = ["certificate", "candidate_issuer"]


class SubjectAlternativeName(OOI):
    """Represents alternative subject names in X509 Certificate objects."""

    certificate: Reference = ReferenceField(X509Certificate)

    _natural_key_attrs = ["certificate"]


class SubjectAlternativeNameHostname(SubjectAlternativeName):
    """Represents subject alternative names for hostnames in X509 Certificate objects.

    Possible values
    ---------------
    hostnames

    Example value
    -------------
    mispo.es
    """

    object_type: Literal["SubjectAlternativeNameHostname"] = "SubjectAlternativeNameHostname"
    hostname: Reference = ReferenceField(Hostname, max_issue_scan_level=1, max_inherit_scan_level=0)

    _natural_key_attrs = ["certificate", "hostname"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return reference.tokenized.hostname.name


class SubjectAlternativeNameIP(SubjectAlternativeName):
    """Represents subject alternative names for IPs in X509 Certificate objects.

    Possible values
    ---------------
    IPv4 or IPv6 address

    Example value
    -------------
    192.168.1.1
    """

    object_type: Literal["SubjectAlternativeNameIP"] = "SubjectAlternativeNameIP"
    address: Reference = ReferenceField(IPAddress)

    _natural_key_attrs = ["certificate", "address"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return reference.tokenized.address.address


class SubjectAlternativeNameQualifier(SubjectAlternativeName):
    """Represents subject alternative names qualifier in X509 Certificate objects.

    Possible values
    ---------------
    hostnames

    Example value
    -------------
    mispo.es
    """

    object_type: Literal["SubjectAlternativeNameQualifier"] = "SubjectAlternativeNameQualifier"
    name: str

    _natural_key_attrs = ["certificate", "name"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return reference.tokenized.name


class X509CertificateV2(OOI):
    """An X.509 certificate, identified by the SHA-256 fingerprint of its
    DER encoding.

    Fixes the identity problems of X509Certificate: the fingerprint is a
    collision-free content address (lowercase hex SHA-256 of the DER
    encoding), and serial_number is the actual serial number. The
    fingerprint is the identity: every writer observes it, whether by
    computing it from the presented bytes or by obtaining the certificate
    (or its hash) from a third-party source. There is no fallback — a
    certificate that cannot be tied to its SHA-256 is not written.

    subject and issuer are RFC4514 distinguished names. Sources that parse
    the DER provide the full DN; API-based sources provide the DN as their
    API renders it, which may be partial or non-canonical — comparisons
    between DNs are only meaningful within one source.

    The full certificate is carried in raw when the bytes were observed;
    a source that saw only the fingerprint and metadata leaves it unset.

    There is exactly one active certificate object version: V1 is
    deprecated and no longer written.
    """

    object_type: Literal["X509CertificateV2"] = "X509CertificateV2"

    # Identity when the bytes were observed: lowercase hex SHA-256 of the
    # DER encoding (the hash of raw).
    fingerprint: str | None = None

    # The full certificate: base64-encoded DER, no PEM armor. Filled when
    # the bytes were observed; API sources leave it unset.
    raw: str | None = None

    # Full RFC4514 distinguished names.
    subject: str | None = None
    issuer: str | None = None

    # Actual serial number: lowercase hex, minimal (no leading zeros),
    # normalized by the writer. The DER path uses format(n, "x"); sources
    # rendering serials differently convert at their boundary.
    serial_number: str | None = None

    valid_from: str
    valid_until: str

    # Public-key algorithm family as a free string, e.g. "RSA", "EC", "Ed25519",
    # "ML-DSA-65". Deliberately not an enum: families evolve (PQC), and sizes
    # are only comparable within a family, so they are not stored.
    pk_algorithm: str | None = None

    # Verified issuer relationship, set by the normalizer after cryptographic
    # verification. Supports aggregation queries such as revocation impact.
    signed_by: Reference | None = ReferenceField(
        "X509CertificateV2", max_issue_scan_level=1, max_inherit_scan_level=0, default=None
    )

    _natural_key_attrs = ["fingerprint"]

    _reverse_relation_names = {"signed_by": "signed_certificates_v2"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"Certificate {reference.natural_key[:16]}"


class SubjectAlternativeNameIPV2(OOI):
    """A subject alternative name that is an IP address, on an
    X509CertificateV2.

    Mirrors SubjectAlternativeNameIP for the fingerprint-identified
    certificate.
    """

    object_type: Literal["SubjectAlternativeNameIPV2"] = "SubjectAlternativeNameIPV2"

    certificate: Reference = ReferenceField(X509CertificateV2, max_issue_scan_level=1, max_inherit_scan_level=0)
    address: Reference = ReferenceField(IPAddress, max_issue_scan_level=4, max_inherit_scan_level=0)

    _natural_key_attrs = ["certificate", "address"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return reference.tokenized.address.address


class SubjectAlternativeNameHostnameV2(OOI):
    """A subject alternative name that is a hostname, on an X509CertificateV2.

    Mirrors SubjectAlternativeNameHostname for the fingerprint-identified
    certificate.
    """

    object_type: Literal["SubjectAlternativeNameHostnameV2"] = "SubjectAlternativeNameHostnameV2"

    certificate: Reference = ReferenceField(X509CertificateV2, max_issue_scan_level=1, max_inherit_scan_level=0)
    hostname: Reference = ReferenceField(Hostname, max_issue_scan_level=1, max_inherit_scan_level=0)

    _natural_key_attrs = ["certificate", "hostname"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return reference.tokenized.hostname.name


class SubjectAlternativeNameQualifierV2(OOI):
    """A subject alternative name that is not a plain hostname (e.g. a
    wildcard), on an X509CertificateV2.

    Mirrors SubjectAlternativeNameQualifier for the fingerprint-identified
    certificate.
    """

    object_type: Literal["SubjectAlternativeNameQualifierV2"] = "SubjectAlternativeNameQualifierV2"

    certificate: Reference = ReferenceField(X509CertificateV2, max_issue_scan_level=1, max_inherit_scan_level=0)
    name: str

    _natural_key_attrs = ["certificate", "name"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return reference.tokenized.name


class TLSCertificateChain(OOI):
    """A certificate presentation observed at a TLS endpoint.

    Records what the server actually transmitted for a specific server name —
    not a reconstructed trust path. The endpoint is a HostnameIPService; a
    connection made without SNI is a presentation of the IPService itself
    (exactly one of the two references is set): it is valid for the null
    server name only, not for the service's other hostnames.

    presented_certificates is ordered leaf-first as received. Entries that
    failed to parse produce no certificate object; the normalizer emits a
    Finding on the chain for each, with position and raw hash as proof.

    Note: XTDB stores multi-valued attributes as sets, so the transmitted
    order is not guaranteed to survive traversal. The order is preserved in
    the presentation_hash (computed over the ordered entries at observation
    time) and the wire order is re-derivable from raw scanner output in
    Bytes. Chain-completeness assessment does not depend on intermediate
    ordering; the leaf is always the first entry presented.
    """

    object_type: Literal["TLSCertificateChain"] = "TLSCertificateChain"

    # The endpoint this presentation was observed on. SNI-qualified endpoints
    # reference the HostnameIPService; connections without a server name
    # reference the IPService. Exactly one of the two is set.
    hostname_ip_service: Reference | None = ReferenceField(HostnameIPService, default=None,
                                                           max_issue_scan_level=0, max_inherit_scan_level=4)
    ip_service: Reference | None = ReferenceField(IPService, default=None,
                                                  max_issue_scan_level=0, max_inherit_scan_level=4)

    # Full chain hash: SHA-256 over length-prefixed SHA-256 hashes of every raw
    # presented entry, in wire order — including entries that failed to parse.
    # Not just the leaf; excludes client capabilities and observation time.
    # Part of the OOI's identity. Computed by the normalizer, not the model.
    presentation_hash: str

    # The certificates that parsed, leaf-first as transmitted. Entries that
    # failed to parse produce no certificate object; the normalizer emits a
    # Finding on the chain for each, with position and raw hash as proof.
    presented_certificates: list[Reference] = ReferenceField(
        X509CertificateV2, default_factory=list, max_issue_scan_level=1, max_inherit_scan_level=0
    )

    _natural_key_attrs = ["ip_service", "presentation_hash"]

    @property
    def natural_key(self) -> str:
        # Mirror TLSCipher: the key is the endpoint's key plus the presentation
        # hash. SNI-qualified endpoints key on the HostnameIPService (which
        # embeds the IPService key); null-SNI presentations key on the
        # IPService itself.
        if self.hostname_ip_service is not None:
            return f"{self.hostname_ip_service.natural_key}|{self.presentation_hash}"
        return f"{self.ip_service.natural_key}|{self.presentation_hash}"

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        # The reference is a tokenized natural key of an IPService (which is
        # network|address|protocol|port|service) plus the presentation hash:
        #   network|address|protocol|port|service|presentation_hash
        # or, SNI-qualified, with the hostname's network|hostname appended
        # before the presentation hash:
        #   network|address|protocol|port|service|hn_network|hostname|presentation_hash
        parts = reference.natural_key.split("|")
        address = parts[1]
        port = parts[3]
        if len(parts) == 8:
            return f"Certificate chain of {parts[6]}:{port} @ {address}"
        return f"Certificate chain of {address}:{port}"


X509Certificate.model_rebuild()
CertificateIssuerCandidate.model_rebuild()
X509CertificateV2.model_rebuild()
TLSCertificateChain.model_rebuild()
SubjectAlternativeNameHostname.model_rebuild()
SubjectAlternativeNameIP.model_rebuild()
SubjectAlternativeNameQualifier.model_rebuild()
SubjectAlternativeNameHostnameV2.model_rebuild()
SubjectAlternativeNameIPV2.model_rebuild()
SubjectAlternativeNameQualifierV2.model_rebuild()
