import datetime
import json
import logging
from collections.abc import Iterable

from dateutil.parser import parse

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models.ooi.certificate import X509Certificate
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


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    results = json.loads(raw)
    fqdn = input_ooi["hostname"]["name"]
    current = fqdn.lstrip(".")

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

        # Yield only current certs.
        expires_in = parse(certificate["not_after"]).astimezone(datetime.timezone.utc) - datetime.datetime.now(
            datetime.timezone.utc
        )
        if expires_in.total_seconds() > 0:
            yield X509Certificate(
                subject=common_name,
                issuer=certificate["issuer_name"],
                valid_from=certificate["not_before"],
                valid_until=certificate["not_after"],
                serial_number=certificate["serial_number"].upper(),
                expires_in=expires_in,
            )
        # walk over the common_name. which might be unrelated to the requested domain, or it might be a parent domain
        # which our dns Boefje should also have picked up.
        # wildcards also trigger here, and won't be visible from a DNS query
        common_identity = _clean_identity(common_name)
        if common_identity is not None and (common_identity.endswith(current) or common_identity not in unique_domains):
            try:
                yield Hostname(name=common_identity, network=network_reference)
            except ValueError:
                logger.debug("Skipping invalid crt.sh common_name %r", common_name)
