import base64
import hashlib
import json
import logging
from collections.abc import Iterable

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, mldsa, rsa

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models.ooi.certificate import X509CertificateV2
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network

logger = logging.getLogger(__name__)


def _clean_identity(identity: str) -> str | None:
    """Normalise a crt.sh certificate identity into a valid hostname, or None.

    crt.sh's ``common_name`` and ``name_value`` can contain wildcard identities
    (``*.example.com``) and rfc822 (email) identities (``admin@example.com``).
    Neither is a valid Hostname: ``*`` and ``@`` are rejected by the Hostname
    validator. Left unchecked, a single such identity raises a ValidationError
    that aborts the whole normalizer run and drops every hostname and
    certificate found in the scan (the runner materializes the generator, so an
    exception discards everything already yielded).
    """
    name = identity.strip().lstrip(".*")
    if not name or "@" in name:
        return None
    return name


def _load_certificate(body: str) -> x509.Certificate:
    """Parse the downloaded /?d=<id> body. It is observed to be PEM; tolerate
    a bare DER body in case crt.sh changes its mind."""
    data = body.strip().encode()
    if data.startswith(b"-----BEGIN CERTIFICATE-----"):
        return x509.load_pem_x509_certificate(data)
    return x509.load_der_x509_certificate(data)


def _pk_algorithm(public_key) -> str:
    """Same semantics as the ssl_certificates normalizer: a free-string
    family, no sizes (not comparable across families, derivable from raw)."""
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


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    results = json.loads(raw)
    fqdn = input_ooi["hostname"]["name"]

    network = Network(name="internet")  # crt.sh only ever sees the Internet
    network_reference = network.reference

    unique_domains = set()
    for certificate in results:
        common_name = certificate["common_name"].lower().lstrip(".*")

        # walk over all name_value parts (possibly just one, possibly more)
        names = certificate["name_value"].lower().splitlines()
        for name in names:
            # todo: do we want to hint other unrelated hostnames using the same certificate / and this possibly
            #  the same private keys for tls?
            name = _clean_identity(name)
            if name is None or name in unique_domains:
                continue
            try:
                hostname = Hostname(name=name, network=network_reference)
            except ValueError:
                logger.debug("Skipping invalid crt.sh identity %r", name)
                continue
            yield hostname
            unique_domains.add(name)

        pem = certificate.get("pem")
        if not pem:
            # No PEM downloaded (historical entry, rate limit, or download
            # failure): no certificate is emitted. A placeholder without a
            # fingerprint would get a degenerate primary key — never write one.
            continue
        try:
            parsed = _load_certificate(pem)
        except (ValueError, TypeError):
            logger.warning("Skipping unparseable certificate body for crt.sh entry %s", certificate.get("id"))
            continue

        der = parsed.public_bytes(serialization.Encoding.DER)
        yield X509CertificateV2(
            fingerprint=hashlib.sha256(der).hexdigest(),
            raw=base64.b64encode(der).decode(),
            subject=parsed.subject.rfc4514_string(),
            issuer=parsed.issuer.rfc4514_string(),
            serial_number=format(parsed.serial_number, "x"),
            valid_from=parsed.not_valid_before_utc.isoformat(),
            valid_until=parsed.not_valid_after_utc.isoformat(),
            pk_algorithm=_pk_algorithm(parsed.public_key()),
        )
